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
        # Get counts before deletion
        cursor.execute("SELECT COUNT(*) FROM reading")
        reading_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alert")
        alert_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM event")
        event_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM smoke")
        smoke_count = cursor.fetchone()[0]
        
        print(f"  Found {reading_count} readings, {alert_count} alerts, {event_count} events, {smoke_count} smoke sessions")
        
        # Delete data (readings first since they reference smokes)
        cursor.execute("DELETE FROM reading")
        cursor.execute("DELETE FROM alert")
        cursor.execute("DELETE FROM event")
        cursor.execute("DELETE FROM smoke")
        
        # Reset autoincrement counters (if table exists)
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('reading', 'alert', 'event', 'smoke')")
        except sqlite3.OperationalError:
            pass  # sqlite_sequence doesn't exist yet
        
        conn.commit()
        print("✓ All data cleared successfully!")
        print("  Settings have been preserved")
        
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

