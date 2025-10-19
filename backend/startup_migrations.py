#!/usr/bin/env python3
"""Run startup migrations and optimizations.

This script should be run when the backend starts to ensure
the database is properly configured and optimized.
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run all necessary migrations."""
    logger.info("=" * 60)
    logger.info("RUNNING STARTUP MIGRATIONS")
    logger.info("=" * 60)
    
    try:
        # Import and run index migration
        logger.info("Running index migration...")
        from migrate_add_indexes import migrate
        created, skipped = migrate()
        logger.info(f"✅ Index migration complete: {created} created, {skipped} skipped")
        
        # Run ANALYZE to update statistics
        logger.info("Running ANALYZE to update query planner...")
        from core.db_maintenance import db_maintenance
        db_maintenance.analyze()
        
        # Set optimal pragmas
        logger.info("Setting optimal database pragmas...")
        db_maintenance.optimize()
        
        logger.info("=" * 60)
        logger.info("✅ All startup migrations completed successfully")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)

