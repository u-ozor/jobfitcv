# app/database/init_db.py
# Run once to create jobs.db and its tables.
# Safe to re-run — CREATE TABLE IF NOT EXISTS means existing data is untouched.

import os
import sys

# Allow running as: python app/database/init_db.py from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database.models import Base
from app.database.session import engine


def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"[init_db] tables created (or already exist) at: {engine.url}")


if __name__ == "__main__":
    init_db()
