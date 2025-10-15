"""Add is_paused field to SmokePhase table - Fixed migration."""

import logging
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add is_paused column to smokephase table using ALTER TABLE."""
    try:
        # Connect to database
        conn = sqlite3.connect("smoker.db")
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(smokephase)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_paused' in columns:
            logger.info("Column 'is_paused' already exists in smokephase table")
        else:
            # Add the column
            cursor.execute("""
                ALTER TABLE smokephase 
                ADD COLUMN is_paused BOOLEAN DEFAULT 0
            """)
            conn.commit()
            logger.info("Successfully added 'is_paused' column to smokephase table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(smokephase)")
        columns = [col[1] for col in cursor.fetchall()]
        logger.info(f"smokephase table columns: {columns}")
        
        conn.close()
        logger.info("Migration complete!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    migrate()

