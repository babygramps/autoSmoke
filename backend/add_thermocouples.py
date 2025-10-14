"""Add thermocouple tables to existing database."""

import sys
import logging
from sqlmodel import create_engine, SQLModel
from db.models import Thermocouple, ThermocoupleReading
from db.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_thermocouple_tables():
    """Create thermocouple and thermocouple_reading tables."""
    try:
        # Create only the new tables
        Thermocouple.metadata.create_all(engine)
        ThermocoupleReading.metadata.create_all(engine)
        
        logger.info("✓ Thermocouple tables created successfully")
        
        # Create a default control thermocouple
        from db.session import get_session_sync
        from db.models import Thermocouple as TC
        
        with get_session_sync() as session:
            # Check if any thermocouples exist
            existing = session.query(TC).first()
            if not existing:
                # Create default control thermocouple
                tc = TC(
                    name="Grate",
                    cs_pin=8,  # CE0
                    enabled=True,
                    is_control=True,
                    order=0,
                    color="#ef4444"  # Red
                )
                session.add(tc)
                session.commit()
                logger.info(f"✓ Created default control thermocouple: {tc.name} (ID={tc.id})")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to create thermocouple tables: {e}")
        return False


if __name__ == "__main__":
    logger.info("Adding thermocouple tables to database...")
    success = add_thermocouple_tables()
    sys.exit(0 if success else 1)

