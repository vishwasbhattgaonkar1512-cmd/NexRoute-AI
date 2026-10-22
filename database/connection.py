from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.config import DB_PATH
from database.models import Base

_engine = None
_SessionLocal = None


def _enable_sqlite_fk(dbapi_conn, _record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def get_engine(db_path=None):
    """Engine for the project database (or `db_path`, e.g. a temporary test database)."""
    global _engine
    if db_path is not None:
        eng = create_engine(f"sqlite:///{db_path}", echo=False)
        event.listen(eng, "connect", _enable_sqlite_fk)
        return eng
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        event.listen(_engine, "connect", _enable_sqlite_fk)
    return _engine


def get_session(engine=None):
    global _SessionLocal
    if engine is not None:
        return sessionmaker(bind=engine, expire_on_commit=False)()
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal()


def init_db(drop_existing=False, engine=None):
    """
    Create missing tables and apply additive migrations. drop_existing=True DROPS ALL TABLES
    (only used by `build_database --rebuild`, which makes a backup first).
    """
    from database.migrations import upgrade_schema
    engine = engine or get_engine()
    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return upgrade_schema(engine)
