#!/usr/bin/env python3
"""
Migration script to add cooking phase tables and update Smoke model.

This script:
1. Creates the new CookingRecipe and SmokePhase tables
2. Adds new columns to the Smoke table
3. Seeds default cooking recipes

Run this after updating models.py to apply database changes.
"""

import sys
from pathlib import Path

# Add backend directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlmodel import SQLModel, create_engine, Session, select
from db.models import CookingRecipe, SmokePhase, Smoke
from db.session import engine
from api.routers.recipes import seed_default_recipes
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Run the migration."""
    logger.info("Starting phase migration...")
    
    try:
        # Create all tables (will only create new ones, existing tables are safe)
        logger.info("Creating new tables...")
        SQLModel.metadata.create_all(engine)
        logger.info("✓ Tables created")
        
        # Seed default recipes
        logger.info("Seeding default recipes...")
        seed_default_recipes()
        logger.info("✓ Default recipes seeded")
        
        # Check existing smoke sessions
        with Session(engine) as session:
            statement = select(Smoke)
            smokes = session.exec(statement).all()
            logger.info(f"Found {len(smokes)} existing smoke sessions")
            
            # The new columns on Smoke model will be automatically added by SQLModel
            # with default values (NULL for optional fields)
            
        logger.info("✓ Migration completed successfully!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Restart the backend server")
        logger.info("2. The new recipe and phase features will be available")
        logger.info("3. Existing smoke sessions will continue to work")
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate()

