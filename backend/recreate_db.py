#!/usr/bin/env python3
"""
Recreate database with new schema including Smoke sessions.
WARNING: This will delete all data!
"""

import sys
from pathlib import Path
from sqlmodel import SQLModel, create_engine

# Import all models
from db.models import Smoke, Reading, Alert, Event, Settings


def recreate_database(db_path: str = "./smoker.db"):
    """Drop all tables and recreate with new schema."""
    
    db_file = Path(db_path)
    
    print(f"Recreating database at {db_path}...")
    print("⚠️  WARNING: This will delete ALL existing data!")
    
    # Delete existing database
    if db_file.exists():
        db_file.unlink()
        print(f"  Deleted existing database")
    
    # Create engine
    engine = create_engine(f"sqlite:///{db_path}")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    print("✓ Database recreated with new schema!")
    print("  Tables created: smoke, reading, alert, event, settings")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        recreate_database(sys.argv[1])
    else:
        recreate_database()

