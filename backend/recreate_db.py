#!/usr/bin/env python3
"""
Recreate database with new schema.
WARNING: This will delete all data!
"""

import sys
from pathlib import Path
from sqlmodel import SQLModel, create_engine

# Import all models to ensure they're registered with SQLModel
from db.models import (
    CookingRecipe,
    Smoke, 
    SmokePhase,
    Thermocouple,
    Reading, 
    ThermocoupleReading,
    Alert, 
    Event, 
    Settings
)


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
    print("  Tables created:")
    print("    - cookingrecipe (recipe templates)")
    print("    - smoke (smoke sessions)")
    print("    - smokephase (cooking phases)")
    print("    - thermocouple (thermocouple config)")
    print("    - reading (temperature readings)")
    print("    - thermocouplereadings (individual TC readings)")
    print("    - alert (alerts and alarms)")
    print("    - event (system events)")
    print("    - settings (system settings)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        recreate_database(sys.argv[1])
    else:
        recreate_database()

