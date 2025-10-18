#!/usr/bin/env python3
"""
Clear all readings, alerts, events, and smoke sessions from the database.
Settings, thermocouples, and recipes are preserved.
"""

import sqlite3
import sys
from pathlib import Path


def clear_data(db_path: str = "./smoker.db"):
    """
    Clear readings, alerts, events, and smoke sessions from database.
    
    PRESERVES:
    - Settings (singleton configuration)
    - Thermocouples (sensor configuration)
    - CookingRecipes (recipe templates)
    
    CLEARS:
    - Readings (sensor data)
    - ThermocoupleReadings (individual sensor readings)
    - Alerts (all alerts and alarms)
    - Events (system events log)
    - Smoke sessions (all smoking sessions)
    - SmokePhases (phase tracking for sessions)
    """
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"✗ Database not found at {db_path}")
        print(f"  Expected path: {db_file.absolute()}")
        return False
    
    print(f"🗑️  Clearing data from {db_path}...")
    print(f"   Database file: {db_file.absolute()}")
    print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Helper function to safely get count
        def safe_count(table_name):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                return cursor.fetchone()[0]
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  Warning: Could not count {table_name}: {e}")
                return 0  # Table doesn't exist
        
        # Helper function to safely delete
        def safe_delete(table_name):
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                deleted_count = cursor.rowcount
                return (True, deleted_count)
            except sqlite3.OperationalError as e:
                print(f"  ⚠️  Warning: Could not delete from {table_name}: {e}")
                return (False, 0)
            except sqlite3.IntegrityError as e:
                print(f"  ✗ Error: Foreign key constraint violation in {table_name}: {e}")
                return (False, 0)
        
        # Get counts before deletion (for reporting)
        print("📊 Scanning database...")
        reading_count = safe_count("reading")
        tc_reading_count = safe_count("thermocouplereadings")
        alert_count = safe_count("alert")
        event_count = safe_count("event")
        smoke_count = safe_count("smoke")
        phase_count = safe_count("smokephase")
        
        # Count preserved items
        settings_count = safe_count("settings")
        thermocouple_count = safe_count("thermocouple")
        recipe_count = safe_count("cookingrecipe")
        
        print(f"  📈 {reading_count:,} readings")
        print(f"  🌡️  {tc_reading_count:,} thermocouple readings")
        print(f"  🚨 {alert_count:,} alerts")
        print(f"  📝 {event_count:,} events")
        print(f"  🔥 {smoke_count:,} smoke sessions")
        print(f"  📊 {phase_count:,} smoke phases")
        print()
        print(f"  ✅ Preserving: {thermocouple_count} thermocouples, {recipe_count} recipes, {settings_count} settings")
        print()
        
        if (reading_count + tc_reading_count + alert_count + event_count + smoke_count + phase_count) == 0:
            print("✓ Database is already empty (nothing to clear)")
            return True
        
        # Confirm with user if running interactively
        if sys.stdout.isatty():
            response = input("⚠️  This will permanently delete all data. Continue? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("❌ Cancelled by user")
                return False
            print()
        
        print("🧹 Clearing data...")
        
        # Delete data (in order to respect foreign key constraints)
        # Children must be deleted before parents
        tables_to_clear = [
            ("thermocouplereadings", "Thermocouple readings"),  # References reading
            ("reading", "Main readings"),                       # References smoke
            ("smokephase", "Smoke phases"),                     # References smoke
            ("smoke", "Smoke sessions"),                        # Parent of readings & phases
            ("alert", "Alerts"),                                # Independent
            ("event", "Events"),                                # Independent
        ]
        
        deleted_summary = []
        total_deleted = 0
        
        for table_name, description in tables_to_clear:
            success, count = safe_delete(table_name)
            if success:
                deleted_summary.append(f"  ✓ {description}: {count:,} rows")
                total_deleted += count
            else:
                deleted_summary.append(f"  ⚠️  {description}: skipped (table not found or error)")
        
        print("\n".join(deleted_summary))
        print()
        
        # Reset autoincrement counters
        print("🔄 Resetting autoincrement counters...")
        try:
            # Get list of sequences that were actually deleted
            cleared_table_names = [name for name, _ in tables_to_clear]
            placeholders = ','.join(['?' for _ in cleared_table_names])
            cursor.execute(f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})", cleared_table_names)
            reset_count = cursor.rowcount
            print(f"  ✓ Reset {reset_count} autoincrement counter(s)")
        except sqlite3.OperationalError:
            print(f"  ℹ️  No autoincrement counters to reset")
        
        # Verify deletion
        print()
        print("🔍 Verifying deletion...")
        remaining_readings = safe_count("reading")
        remaining_tc_readings = safe_count("thermocouplereadings")
        remaining_alerts = safe_count("alert")
        remaining_events = safe_count("event")
        remaining_smokes = safe_count("smoke")
        remaining_phases = safe_count("smokephase")
        
        total_remaining = (remaining_readings + remaining_tc_readings + remaining_alerts + 
                          remaining_events + remaining_smokes + remaining_phases)
        
        if total_remaining > 0:
            print(f"  ⚠️  Warning: {total_remaining} rows still remain!")
            print(f"     Readings: {remaining_readings}, TC Readings: {remaining_tc_readings}")
            print(f"     Alerts: {remaining_alerts}, Events: {remaining_events}")
            print(f"     Smokes: {remaining_smokes}, Phases: {remaining_phases}")
            return False
        else:
            print(f"  ✓ All data cleared: {total_deleted:,} total rows deleted")
        
        # VACUUM to reclaim space
        print()
        print("💾 Optimizing database (VACUUM)...")
        conn.commit()  # Must commit before VACUUM
        cursor.execute("VACUUM")
        print("  ✓ Database optimized")
        
        conn.commit()
        
        print()
        print("=" * 60)
        print("✅ SUCCESS: All data cleared!")
        print("=" * 60)
        print(f"📊 Summary:")
        print(f"  • Deleted {total_deleted:,} total rows")
        print(f"  • Preserved {thermocouple_count} thermocouples")
        print(f"  • Preserved {recipe_count} recipes")
        print(f"  • Preserved {settings_count} settings entry")
        print()
        print("ℹ️  To completely reset the database (including settings),")
        print("   run: python recreate_db.py")
        print()
        
        return True
        
    except sqlite3.Error as e:
        print()
        print(f"✗ ERROR: Failed to clear data: {e}")
        print(f"  Rolling back transaction...")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        success = clear_data(sys.argv[1])
    else:
        success = clear_data()
    
    sys.exit(0 if success else 1)

