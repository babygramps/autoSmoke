#!/usr/bin/env python3
"""
Add new columns to existing Smoke table for phase support.
This preserves existing session data.
"""

import sys
import sqlite3
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from db.session import engine
from sqlmodel import SQLModel, create_engine, Session
from api.routers.recipes import seed_default_recipes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add new columns to Smoke table and create new tables."""
    
    # Get database path from engine URL
    db_path = str(engine.url).replace('sqlite:///', '')
    
    logger.info(f"Migrating database: {db_path}")
    
    try:
        # Connect directly with sqlite3 for ALTER TABLE commands
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(smoke)")
        columns = [col[1] for col in cursor.fetchall()]
        
        new_columns = [
            ("recipe_id", "INTEGER"),
            ("recipe_config", "VARCHAR"),
            ("current_phase_id", "INTEGER"),
            ("meat_target_temp_f", "FLOAT"),
            ("meat_probe_tc_id", "INTEGER"),
            ("pending_phase_transition", "BOOLEAN DEFAULT 0"),
        ]
        
        logger.info("Adding new columns to Smoke table...")
        for col_name, col_type in new_columns:
            if col_name not in columns:
                try:
                    sql = f"ALTER TABLE smoke ADD COLUMN {col_name} {col_type}"
                    logger.info(f"  Adding column: {col_name}")
                    cursor.execute(sql)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        raise
                    logger.info(f"  Column {col_name} already exists, skipping")
            else:
                logger.info(f"  Column {col_name} already exists, skipping")
        
        conn.commit()
        conn.close()
        
        logger.info("✓ Smoke table updated")
        
        # Now create new tables using SQLModel
        logger.info("Creating new tables (CookingRecipe, SmokePhase)...")
        SQLModel.metadata.create_all(engine)
        logger.info("✓ New tables created")
        
        # Seed default recipes
        logger.info("Seeding default recipes...")
        seed_default_recipes()
        logger.info("✓ Default recipes seeded")
        
        logger.info("")
        logger.info("✓ Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Restart the backend server")
        logger.info("2. The new recipe and phase features will be available")
        logger.info("3. Existing smoke sessions have been preserved")
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate()

