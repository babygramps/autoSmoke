#!/usr/bin/env python3
"""
Clear all readings, alerts, events, and smoke sessions from the database.
Settings are preserved.
"""

import sqlite3
import sys
from pathlib import Path


def clear_data(db_path: str = "./smoker.db"):
    """Clear readings, alerts, events, and smoke sessions from database."""
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"Database not found at {db_path}")
        return
    
    print(f"Clearing data from {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Helper function to safely get count
        def safe_count(table_name):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
            except sqlite3.OperationalError:
                return 0  # Table doesn't exist
        
        # Helper function to safely delete
        def safe_delete(table_name):
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                return True
            except sqlite3.OperationalError:
                return False  # Table doesn't exist
        
        # Get counts before deletion
        reading_count = safe_count("reading")
        tc_reading_count = safe_count("thermocouplereadings")
        alert_count = safe_count("alert")
        event_count = safe_count("event")
        smoke_count = safe_count("smoke")
        phase_count = safe_count("smokephase")
        
        print(f"  Found {reading_count} readings, {tc_reading_count} thermocouple readings")
        print(f"  Found {alert_count} alerts, {event_count} events")
        print(f"  Found {smoke_count} smoke sessions, {phase_count} smoke phases")
        
        # Delete data (in order to respect foreign key constraints)
        tables_to_clear = [
            "thermocouplereadings",  # References reading
            "reading",               # References smoke
            "smokephase",            # References smoke
            "smoke",                 # Parent table
            "alert",                 # Independent
            "event",                 # Independent
        ]
        
        deleted_tables = []
        for table in tables_to_clear:
            if safe_delete(table):
                deleted_tables.append(table)
        
        print(f"  Cleared tables: {', '.join(deleted_tables)}")
        
        # Reset autoincrement counters (if table exists)
        try:
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({','.join(['?' for _ in deleted_tables])})", deleted_tables)
        except sqlite3.OperationalError:
            pass  # sqlite_sequence doesn't exist yet
        
        conn.commit()
        print("✓ All data cleared successfully!")
        print("  Settings, thermocouples, and recipes have been preserved")
        
    except sqlite3.Error as e:
        print(f"✗ Failed to clear data: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        clear_data(sys.argv[1])
    else:
        clear_data()

