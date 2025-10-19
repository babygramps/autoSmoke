"""Add database indexes for performance optimization.

This migration adds critical indexes to improve query performance,
especially with large datasets (30k+ readings).
"""

import logging
from sqlmodel import create_engine, text
from db.session import get_session_sync
from db.models import DBSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add performance-critical indexes to the database."""
    
    logger.info("=" * 60)
    logger.info("Starting index migration for performance optimization")
    logger.info("=" * 60)
    
    with get_session_sync() as session:
        connection = session.connection()
        
        # List of indexes to create
        indexes = [
            # Reading table indexes - most critical for performance
            ("idx_reading_ts", "reading", "ts"),
            ("idx_reading_smoke_id", "reading", "smoke_id"),
            ("idx_reading_ts_smoke_id", "reading", "ts, smoke_id"),  # Composite for filtered queries
            
            # ThermocoupleReading indexes
            ("idx_tc_reading_reading_id", "thermocouplereading", "reading_id"),
            ("idx_tc_reading_tc_id", "thermocouplereading", "thermocouple_id"),
            
            # Alert indexes
            ("idx_alert_ts", "alert", "ts"),
            ("idx_alert_active", "alert", "active"),
            ("idx_alert_ts_active", "alert", "ts, active"),  # Composite for active alerts query
            
            # Event indexes
            ("idx_event_ts", "event", "ts"),
            ("idx_event_kind", "event", "kind"),
            
            # Smoke session indexes
            ("idx_smoke_started_at", "smoke", "started_at"),
            ("idx_smoke_is_active", "smoke", "is_active"),
            
            # SmokePhase indexes
            ("idx_phase_smoke_id", "smokephase", "smoke_id"),
            ("idx_phase_is_active", "smokephase", "is_active"),
        ]
        
        created_count = 0
        skipped_count = 0
        
        for idx_name, table_name, columns in indexes:
            try:
                # Check if index already exists
                result = connection.execute(text(
                    f"SELECT name FROM sqlite_master WHERE type='index' AND name='{idx_name}'"
                )).fetchone()
                
                if result:
                    logger.info(f"  ⏭️  Index '{idx_name}' already exists, skipping")
                    skipped_count += 1
                    continue
                
                # Create the index
                logger.info(f"  ✨ Creating index '{idx_name}' on {table_name}({columns})")
                connection.execute(text(
                    f"CREATE INDEX {idx_name} ON {table_name}({columns})"
                ))
                created_count += 1
                logger.info(f"  ✅ Index '{idx_name}' created successfully")
                
            except Exception as e:
                logger.error(f"  ❌ Failed to create index '{idx_name}': {e}")
        
        # Commit the changes
        session.commit()
        
        logger.info("=" * 60)
        logger.info(f"Index migration complete!")
        logger.info(f"  Created: {created_count} indexes")
        logger.info(f"  Skipped: {skipped_count} indexes (already exist)")
        logger.info("=" * 60)
        
        # Run ANALYZE to update query planner statistics
        logger.info("Running ANALYZE to update query planner statistics...")
        connection.execute(text("ANALYZE"))
        session.commit()
        logger.info("✅ ANALYZE complete")
        
        return created_count, skipped_count


if __name__ == "__main__":
    try:
        created, skipped = migrate()
        logger.info(f"\n✅ Migration successful: {created} indexes created, {skipped} skipped")
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

