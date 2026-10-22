from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import DB_PATH
from database.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db(drop_existing=False):
    engine = get_engine()
    if drop_existing:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # no-op on tables that already exist -> persistent across runs
