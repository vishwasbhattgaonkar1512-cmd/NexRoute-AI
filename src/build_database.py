"""
Phase 2: build/populate the SQLite database from cleaned data + master config.
Idempotent: safe to re-run (will not duplicate rows, uses --rebuild to fully reset).
"""
import sys
import argparse
from database.connection import init_db, get_session
from database.models import (
    Factory, Product, Customer, Order, OrderItem, ProductFactoryAssignment,
    FinancialAssumption, OptimizationSetting, DataQualityLog
)
from src.config import FACTORIES, PRODUCT_FACTORY_BASELINE, FINANCIAL_ASSUMPTIONS, STATE_CENTROIDS
from src.preprocessing import run_pipeline


def build(rebuild=False):
    init_db(drop_existing=rebuild)
    session = get_session()

    # --- factories ---
    factory_name_to_id = {}
    for f in FACTORIES:
        existing = session.query(Factory).filter_by(factory_name=f["factory_name"]).first()
        if not existing:
            existing = Factory(**f)
            session.add(existing)
            session.flush()
        factory_name_to_id[f["factory_name"]] = existing.factory_id
    session.commit()

    # --- products + baseline assignments ---
    product_name_to_id = {}
    for p in PRODUCT_FACTORY_BASELINE:
        existing = session.query(Product).filter_by(product_name=p["product_name"]).first()
        if not existing:
            existing = Product(product_name=p["product_name"], division=p["division"])
            session.add(existing)
            session.flush()
        product_name_to_id[p["product_name"]] = existing.product_id

        assignment_exists = session.query(ProductFactoryAssignment).filter_by(
            product_id=existing.product_id,
            factory_id=factory_name_to_id[p["factory_name"]],
            assignment_type="baseline",
        ).first()
        if not assignment_exists:
            session.add(ProductFactoryAssignment(
                product_id=existing.product_id,
                factory_id=factory_name_to_id[p["factory_name"]],
                assignment_type="baseline",
                is_compatible=True,
                is_current=True,
            ))
    session.commit()

    # --- financial assumptions ---
    for name, cfg in FINANCIAL_ASSUMPTIONS.items():
        existing = session.query(FinancialAssumption).filter_by(assumption_name=name).first()
        if not existing:
            session.add(FinancialAssumption(
                assumption_name=name,
                assumption_value=cfg["value"],
                assumption_unit=cfg["unit"],
                assumption_source=cfg["source"],
                is_configurable=cfg["is_configurable"],
            ))
    session.commit()

    # --- default optimization setting ---
    if not session.query(OptimizationSetting).first():
        session.add(OptimizationSetting(
            speed_weight=0.4, profit_weight=0.4, risk_weight=0.2,
            minimum_profit_threshold=0.0, optimization_mode="balanced",
        ))
    session.commit()

    # --- orders, customers, order_items from cleaned pipeline output ---
    df, dq_logs = run_pipeline()

    # clear previous run's order-level data to avoid duplication on re-run (idempotent for this layer only)
    session.query(OrderItem).delete()
    session.query(Order).delete()
    session.query(Customer).delete()
    session.query(DataQualityLog).delete()
    session.commit()

    customer_ids_seen = set()
    for _, row in df.drop_duplicates("Customer ID").iterrows():
        cid = int(row["Customer ID"])
        if cid in customer_ids_seen:
            continue
        customer_ids_seen.add(cid)
        lat, lon = STATE_CENTROIDS.get(row["State/Province"], (None, None))
        session.add(Customer(
            customer_id=cid,
            country_region=row["Country/Region"],
            city=row["City"],
            state_province=row["State/Province"],
            postal_code=row["Postal Code"],
            latitude=lat, longitude=lon,
            region=row["Region"],
        ))
    session.commit()

    orders_seen = set()
    for _, row in df.drop_duplicates("Order ID").iterrows():
        oid = row["Order ID"]
        if oid in orders_seen:
            continue
        orders_seen.add(oid)
        session.add(Order(
            order_id=oid,
            customer_id=int(row["Customer ID"]),
            order_date=row["order_date"],
            ship_date=row["ship_date"],
            ship_mode=row["Ship Mode"],
        ))
    session.commit()

    items = []
    for _, row in df.iterrows():
        pid = product_name_to_id.get(row["Product Name"])
        if pid is None:
            continue
        items.append(OrderItem(
            source_row_id=int(row["Row ID"]),
            order_id=row["Order ID"],
            product_id=pid,
            sales=float(row["Sales"]),
            units=int(row["Units"]),
            gross_profit=float(row["Gross Profit"]),
            cost=float(row["Cost"]),
            lead_time_days_raw=float(row["lead_time_days_raw"]),
            lead_time_index=float(row["lead_time_index"]),
            distance_miles=float(row["distance_miles"]) if row["distance_miles"] == row["distance_miles"] else None,
        ))
    session.bulk_save_objects(items)
    session.commit()

    for log in dq_logs:
        session.add(DataQualityLog(**log))
    session.commit()

    print(f"Database built at data/nassau.db")
    print(f"  Factories: {session.query(Factory).count()}")
    print(f"  Products: {session.query(Product).count()}")
    print(f"  Customers: {session.query(Customer).count()}")
    print(f"  Orders: {session.query(Order).count()}")
    print(f"  Order items: {session.query(OrderItem).count()}")
    print(f"  Data quality logs: {session.query(DataQualityLog).count()}")
    session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="Drop and recreate all tables")
    args = parser.parse_args()
    build(rebuild=args.rebuild)
