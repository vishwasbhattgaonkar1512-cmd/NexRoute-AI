"""
Build / update the SQLite database from the raw CSV.

    python -m src.build_database                 SAFE (default): upgrade schema additively, insert any missing
                                                 master/order rows, refresh DERIVED columns only (recovered lead
                                                 time, flags, distances, order geography), add a new data-quality
                                                 report, register the active model. Never deletes rows.
    python -m src.build_database --rebuild --yes-delete-all-data
                                                 DESTRUCTIVE: copies the database to a timestamped backup, then
                                                 drops and recreates every table. Requires both flags.
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys

import pandas as pd
from sqlalchemy import text

from database.connection import init_db, get_session, get_engine
from database.models import (
    Factory, Product, Customer, Order, OrderItem, ProductFactoryAssignment, FinancialAssumption,
    OptimizationSetting,
)
from src.config import FACTORIES, PRODUCT_FACTORY_BASELINE, FINANCIAL_ASSUMPTIONS, DESTINATION_CENTROIDS, DB_PATH
from src.preprocessing import run_pipeline, write_outputs
from src.persistence import save_data_quality_report, database_statistics


def _none(v):
    return None if pd.isna(v) else v


def backup_database() -> str | None:
    if not DB_PATH.exists():
        return None
    dest = DB_PATH.with_name(f"nassau_backup_{dt.datetime.now():%Y%m%d-%H%M%S}.db")
    shutil.copy2(DB_PATH, dest)
    return str(dest)


def build(rebuild: bool = False, engine=None, df: pd.DataFrame | None = None, issues: list | None = None,
          register_model: bool = True, verbose: bool = True) -> dict:
    report = {"actions": []}
    if rebuild and engine is None:
        report["backup"] = backup_database()
    report["actions"] += init_db(drop_existing=rebuild, engine=engine)
    if df is None:
        df, issues = run_pipeline()
        write_outputs(df, issues)
    s = get_session(engine) if engine is not None else get_session()

    # --- master data (insert missing only) ---
    fid = {}
    for f in FACTORIES:
        row = s.query(Factory).filter_by(factory_name=f["factory_name"]).first()
        if row is None:
            row = Factory(**f)
            s.add(row)
            s.flush()
        fid[f["factory_name"]] = row.factory_id
    src_pid = df.groupby("Product Name")["Product ID"].first().to_dict()
    pid = {}
    for p in PRODUCT_FACTORY_BASELINE:
        row = s.query(Product).filter_by(product_name=p["product_name"]).first()
        if row is None:
            row = Product(product_name=p["product_name"], division=p["division"])
            s.add(row)
            s.flush()
        if row.division != p["division"]:  # e.g. Fizzy Lifting Drinks corrected to Sugar
            report["actions"].append(f"product division {row.product_name}: {row.division} -> {p['division']}")
            row.division = p["division"]
        row.source_product_id = row.source_product_id or src_pid.get(p["product_name"])
        pid[p["product_name"]] = row.product_id
        if not s.query(ProductFactoryAssignment).filter_by(product_id=row.product_id, factory_id=fid[p["factory_name"]],
                                                          assignment_type="baseline").first():
            s.add(ProductFactoryAssignment(product_id=row.product_id, factory_id=fid[p["factory_name"]],
                                           assignment_type="baseline", is_compatible=True, is_current=True))
    for name, cfg in FINANCIAL_ASSUMPTIONS.items():
        if not s.query(FinancialAssumption).filter_by(assumption_name=name).first():
            s.add(FinancialAssumption(assumption_name=name, assumption_value=cfg["value"], assumption_unit=cfg["unit"],
                                      assumption_source=cfg["source"], is_configurable=cfg["is_configurable"]))
            report["actions"].append(f"added assumption {name}")
    if not s.query(OptimizationSetting).first():
        s.add(OptimizationSetting(speed_weight=0.4, profit_weight=0.4, risk_weight=0.2,
                                  minimum_profit_threshold=0.0, optimization_mode="balanced"))
    s.commit()

    # --- customers / orders / order items: insert missing ---
    have_c = {c for (c,) in s.query(Customer.customer_id).all()}
    new_c = []
    for _, r in df.drop_duplicates("Customer ID").iterrows():
        cid = int(r["Customer ID"])
        if cid not in have_c:
            lat, lon = DESTINATION_CENTROIDS.get(r["State/Province"], (None, None))
            new_c.append(Customer(customer_id=cid, country_region=r["Country/Region"], city=r["City"],
                                  state_province=r["State/Province"], postal_code=r["Postal Code"],
                                  latitude=lat, longitude=lon, region=r["Region"]))
    s.add_all(new_c)
    s.commit()
    have_o = {o for (o,) in s.query(Order.order_id).all()}
    new_o = [Order(order_id=r["Order ID"], customer_id=int(r["Customer ID"]), order_date=r["order_date"],
                   ship_date=r["ship_date"], ship_mode=r["Ship Mode"])
             for _, r in df.drop_duplicates("Order ID").iterrows() if r["Order ID"] not in have_o]
    s.add_all(new_o)
    s.commit()
    have_i = {i for (i,) in s.query(OrderItem.source_row_id).all()}
    new_i = [OrderItem(source_row_id=int(r["Row ID"]), order_id=r["Order ID"], product_id=pid[r["Product Name"]],
                       sales=float(r["Sales"]), units=int(r["Units"]), gross_profit=float(r["Gross Profit"]),
                       cost=float(r["Cost"]), lead_time_days_raw=float(r["lead_time_days_raw"]),
                       lead_time_index=float(r["lead_time_index"]))
             for _, r in df.iterrows() if int(r["Row ID"]) not in have_i and r["Product Name"] in pid]
    s.bulk_save_objects(new_i)
    s.commit()
    report["inserted"] = {"customers": len(new_c), "orders": len(new_o), "order_items": len(new_i)}

    # --- refresh DERIVED columns only (raw source values are never changed) ---
    conn = s.connection()
    items = [{"rid": int(r["Row ID"]), "lr": _none(r["lead_time_recovered_days"]), "fl": r["lead_time_recovered_flag"],
              "dup": bool(r["is_possible_duplicate"]), "dist": _none(r["distance_miles"])} for _, r in df.iterrows()]
    conn.execute(text("UPDATE order_items SET lead_time_recovered_days=:lr, lead_time_recovered_flag=:fl, "
                      "is_possible_duplicate=:dup, distance_miles=:dist WHERE source_row_id=:rid"), items)
    orders = [{"oid": r["Order ID"], "c": r["Country/Region"], "ci": r["City"], "st": r["State/Province"],
               "pc": r["Postal Code"], "rg": r["Region"],
               "rb": None if pd.isna(r["order_date_rebuilt"]) else r["order_date_rebuilt"].to_pydatetime()}
              for _, r in df.drop_duplicates("Order ID").iterrows()]
    conn.execute(text("UPDATE orders SET ship_country=:c, ship_city=:ci, ship_state=:st, ship_postal_code=:pc, "
                      "ship_region=:rg, order_date_rebuilt=:rb WHERE order_id=:oid"), orders)
    s.commit()
    s.close()
    report["refreshed"] = {"order_items": len(items), "orders": len(orders)}

    report["data_quality_report_id"] = save_data_quality_report(issues or [], engine=engine)

    if register_model:
        try:
            from src.prediction_engine import load_active_model, ACTIVE_POINTER
            from src.persistence import register_model_version
            import json
            _, meta = load_active_model()
            ptr = json.loads(ACTIVE_POINTER.read_text())
            report["model_registry_id"] = register_model_version(meta, ptr["model_path"], engine=engine)
        except FileNotFoundError as exc:
            report["actions"].append(f"model not registered: {exc}")

    stats = database_statistics(engine or get_engine())
    report["table_rows"] = dict(zip(stats["table"], stats["rows"]))
    if verbose:
        if report.get("backup"):
            print(f"Backup written to {report['backup']}")
        for a in report["actions"]:
            print("  " + a)
        print(f"Inserted: {report['inserted']}  Refreshed derived columns: {report['refreshed']}")
        print(f"Data-quality report: {report['data_quality_report_id']}")
        for t, n in report["table_rows"].items():
            print(f"  {t:32} {n:>7}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rebuild", action="store_true", help="DESTRUCTIVE: drop and recreate all tables (backup first)")
    ap.add_argument("--yes-delete-all-data", action="store_true", help="required together with --rebuild")
    args = ap.parse_args()
    if args.rebuild and not args.yes_delete_all_data:
        sys.exit("Refusing to rebuild: --rebuild deletes every table. Add --yes-delete-all-data to confirm "
                 "(a timestamped backup of data/nassau.db is made first).")
    build(rebuild=args.rebuild)
