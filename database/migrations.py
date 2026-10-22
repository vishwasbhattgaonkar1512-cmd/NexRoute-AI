"""
Additive schema migrations for SQLite.

upgrade_schema() compares the ORM models with the live database and:
  * creates missing tables;
  * adds missing columns with ALTER TABLE ... ADD COLUMN (always nullable, no data rewritten);
  * creates missing indexes. A UNIQUE index is created only if the existing data has no duplicates;
    otherwise it is skipped and reported.
It never drops or renames anything and never deletes rows.
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from database.models import Base


def upgrade_schema(engine) -> list[str]:
    actions = []
    Base.metadata.create_all(engine)  # new tables only
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in existing:
                    coltype = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'))
                    actions.append(f"added column {table.name}.{col.name}")
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        existing_idx = {i["name"] for i in insp.get_indexes(table.name)}
        for idx in table.indexes:
            if idx.name in existing_idx:
                continue
            if idx.unique:
                cols = ", ".join(f'"{c.name}"' for c in idx.columns)
                with engine.connect() as conn:
                    dup = conn.execute(text(
                        f'SELECT COUNT(*) FROM (SELECT {cols} FROM "{table.name}" '
                        f'WHERE {" AND ".join(f"{c.name!s} IS NOT NULL" for c in idx.columns)} '
                        f'GROUP BY {cols} HAVING COUNT(*) > 1)')).scalar()
                if dup:
                    actions.append(f"SKIPPED unique index {idx.name}: {dup} duplicate key groups in existing data")
                    continue
            idx.create(engine, checkfirst=True)
            actions.append(f"created index {idx.name}")
    return actions
