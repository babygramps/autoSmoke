#!/usr/bin/env python3
"""
Database migration script to add control_mode and time_window_s fields.

Run this if you're upgrading from an older version without these fields.
"""

import sqlite3
import sys
from pathlib import Path


def migrate_database(db_path: str = "./smoker.db"):
    """Add control_mode and time_window_s columns to settings table."""
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"Database not found at {db_path}")
        print("No migration needed - database will be created with correct schema.")
        return
    
    print(f"Migrating database at {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        needs_control_mode = 'control_mode' not in columns
        needs_time_window = 'time_window_s' not in columns
        
        if not needs_control_mode and not needs_time_window:
            print("✓ Database already up to date - no migration needed")
            return
        
        # Add control_mode column if missing
        if needs_control_mode:
            print("  Adding control_mode column...")
            cursor.execute("""
                ALTER TABLE settings 
                ADD COLUMN control_mode TEXT DEFAULT 'thermostat'
            """)
            print("  ✓ control_mode column added")
        
        # Add time_window_s column if missing
        if needs_time_window:
            print("  Adding time_window_s column...")
            cursor.execute("""
                ALTER TABLE settings 
                ADD COLUMN time_window_s INTEGER DEFAULT 10
            """)
            print("  ✓ time_window_s column added")
        
        conn.commit()
        print("✓ Migration completed successfully!")
        
    except sqlite3.Error as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        migrate_database(sys.argv[1])
    else:
        migrate_database()

