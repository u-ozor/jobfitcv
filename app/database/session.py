# app/database/session.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///data/jobs.db")

engine = create_engine(
    _DB_PATH,
    connect_args={"check_same_thread": False}  # needed for SQLite + FastAPI
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)


def get_db():
    """FastAPI dependency — yields a DB session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
