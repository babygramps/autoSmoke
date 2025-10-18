"""Migration: Add adaptive_pid_enabled column to settings table."""

import sqlite3
import os
import sys

def migrate():
    """Add adaptive_pid_enabled column to settings table."""
    
    # Get database path
    db_path = os.path.join(os.path.dirname(__file__), "smoker.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("No migration needed (fresh install)")
        return
    
    print(f"Migrating database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'adaptive_pid_enabled' in columns:
            print("✓ Column 'adaptive_pid_enabled' already exists - skipping migration")
            conn.close()
            return
        
        # Add the column with default value True (enabled by default)
        print("Adding 'adaptive_pid_enabled' column...")
        cursor.execute("""
            ALTER TABLE settings 
            ADD COLUMN adaptive_pid_enabled BOOLEAN DEFAULT 1
        """)
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Added 'adaptive_pid_enabled' column (default: True)")
        
        conn.close()
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()

