"""Migration: Fix duplicate CS pin assignments in thermocouple table.

This migration disables any thermocouples that have duplicate CS pin assignments,
keeping only the first (control) thermocouple active on each pin.
"""

import logging
import sys
from db.session import get_session_sync
from db.models import Thermocouple
from sqlmodel import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_fix_duplicate_cs_pins():
    """Fix duplicate CS pin assignments in thermocouple table."""
    try:
        with get_session_sync() as session:
            # Get all enabled thermocouples ordered by ID
            statement = select(Thermocouple).where(Thermocouple.enabled == True).order_by(Thermocouple.id)
            thermocouples = session.exec(statement).all()
            
            if not thermocouples:
                logger.info("No thermocouples found, nothing to migrate")
                return True
            
            # Track CS pins we've seen
            cs_pins_seen = {}
            duplicates_found = []
            
            for tc in thermocouples:
                if tc.cs_pin in cs_pins_seen:
                    # Duplicate found - disable this thermocouple
                    duplicates_found.append((tc.id, tc.name, tc.cs_pin, cs_pins_seen[tc.cs_pin]))
                    tc.enabled = False
                    logger.warning(f"Disabling thermocouple '{tc.name}' (ID={tc.id}) - CS pin {tc.cs_pin} already used by ID {cs_pins_seen[tc.cs_pin]}")
                else:
                    cs_pins_seen[tc.cs_pin] = tc.id
                    logger.info(f"Keeping thermocouple '{tc.name}' (ID={tc.id}) on CS pin {tc.cs_pin}")
            
            if duplicates_found:
                session.commit()
                logger.info("=" * 80)
                logger.info("MIGRATION COMPLETE: Fixed duplicate CS pin assignments")
                logger.info("=" * 80)
                logger.info(f"Disabled {len(duplicates_found)} thermocouple(s) with duplicate CS pins:")
                for tc_id, name, cs_pin, first_tc_id in duplicates_found:
                    logger.info(f"  - '{name}' (ID={tc_id}) on pin {cs_pin} (pin owned by ID={first_tc_id})")
                logger.info("")
                logger.info("To add additional thermocouples:")
                logger.info("  1. Connect them to DIFFERENT CS pins (e.g., GPIO 7, 24, 25)")
                logger.info("  2. Update the thermocouple's cs_pin in the database")
                logger.info("  3. Re-enable the thermocouple")
                logger.info("=" * 80)
            else:
                logger.info("No duplicate CS pins found - database is clean")
            
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("Running migration: Fix duplicate CS pin assignments")
    success = migrate_fix_duplicate_cs_pins()
    sys.exit(0 if success else 1)

