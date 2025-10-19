"""Automatic data cleanup and archival system.

Manages database size by archiving or removing old data while preserving
important session information.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlmodel import select, delete, and_, or_
from db.session import get_session_sync
from db.models import Reading, ThermocoupleReading, Alert, Event, Smoke

logger = logging.getLogger(__name__)


class DataCleanupManager:
    """Manages automatic data cleanup and archival."""
    
    def __init__(self):
        self.retention_days_readings = 30  # Keep readings for 30 days
        self.retention_days_events = 90    # Keep events for 90 days  
        self.retention_days_alerts = 60    # Keep alerts for 60 days
        self.max_readings_per_session = 50000  # Max readings per smoke session
    
    def cleanup_old_data(
        self,
        reading_days: Optional[int] = None,
        event_days: Optional[int] = None,
        alert_days: Optional[int] = None,
        dry_run: bool = False
    ) -> dict:
        """
        Clean up old data from the database.
        
        Args:
            reading_days: Days to keep readings (default: 30)
            event_days: Days to keep events (default: 90)
            alert_days: Days to keep cleared alerts (default: 60)
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dictionary with cleanup statistics
        """
        reading_days = reading_days or self.retention_days_readings
        event_days = event_days or self.retention_days_events
        alert_days = alert_days or self.retention_days_alerts
        
        stats = {
            'readings_deleted': 0,
            'thermocouple_readings_deleted': 0,
            'events_deleted': 0,
            'alerts_deleted': 0,
            'dry_run': dry_run
        }
        
        logger.info("=" * 60)
        logger.info(f"Starting data cleanup (dry_run={dry_run})")
        logger.info(f"  Retention: readings={reading_days}d, events={event_days}d, alerts={alert_days}d")
        logger.info("=" * 60)
        
        with get_session_sync() as session:
            # Calculate cutoff dates
            reading_cutoff = datetime.utcnow() - timedelta(days=reading_days)
            event_cutoff = datetime.utcnow() - timedelta(days=event_days)
            alert_cutoff = datetime.utcnow() - timedelta(days=alert_days)
            
            # Clean up old readings (oldest data, most impact)
            logger.info(f"Cleaning readings older than {reading_cutoff.isoformat()}...")
            
            # Get IDs of readings to delete
            old_readings_query = select(Reading.id).where(Reading.ts < reading_cutoff)
            old_reading_ids = [r[0] for r in session.exec(old_readings_query).all()]
            
            if old_reading_ids:
                logger.info(f"  Found {len(old_reading_ids)} old readings to delete")
                
                if not dry_run:
                    # Delete associated thermocouple readings first (foreign key)
                    tc_delete_stmt = delete(ThermocoupleReading).where(
                        ThermocoupleReading.reading_id.in_(old_reading_ids)
                    )
                    result = session.exec(tc_delete_stmt)
                    stats['thermocouple_readings_deleted'] = result.rowcount
                    logger.info(f"  ✅ Deleted {stats['thermocouple_readings_deleted']} thermocouple readings")
                    
                    # Delete main readings
                    reading_delete_stmt = delete(Reading).where(Reading.id.in_(old_reading_ids))
                    result = session.exec(reading_delete_stmt)
                    stats['readings_deleted'] = result.rowcount
                    logger.info(f"  ✅ Deleted {stats['readings_deleted']} readings")
                else:
                    stats['readings_deleted'] = len(old_reading_ids)
                    logger.info(f"  🔍 Would delete {len(old_reading_ids)} readings (dry run)")
            else:
                logger.info("  ✨ No old readings to delete")
            
            # Clean up old events
            logger.info(f"Cleaning events older than {event_cutoff.isoformat()}...")
            old_events_query = select(Event).where(Event.ts < event_cutoff)
            old_events = session.exec(old_events_query).all()
            
            if old_events:
                logger.info(f"  Found {len(old_events)} old events to delete")
                if not dry_run:
                    for event in old_events:
                        session.delete(event)
                    stats['events_deleted'] = len(old_events)
                    logger.info(f"  ✅ Deleted {stats['events_deleted']} events")
                else:
                    stats['events_deleted'] = len(old_events)
                    logger.info(f"  🔍 Would delete {len(old_events)} events (dry run)")
            else:
                logger.info("  ✨ No old events to delete")
            
            # Clean up old cleared/acknowledged alerts
            logger.info(f"Cleaning cleared alerts older than {alert_cutoff.isoformat()}...")
            old_alerts_query = select(Alert).where(
                and_(
                    Alert.ts < alert_cutoff,
                    or_(
                        Alert.active == False,
                        Alert.acknowledged == True
                    )
                )
            )
            old_alerts = session.exec(old_alerts_query).all()
            
            if old_alerts:
                logger.info(f"  Found {len(old_alerts)} old cleared alerts to delete")
                if not dry_run:
                    for alert in old_alerts:
                        session.delete(alert)
                    stats['alerts_deleted'] = len(old_alerts)
                    logger.info(f"  ✅ Deleted {stats['alerts_deleted']} alerts")
                else:
                    stats['alerts_deleted'] = len(old_alerts)
                    logger.info(f"  🔍 Would delete {len(old_alerts)} alerts (dry run)")
            else:
                logger.info("  ✨ No old alerts to delete")
            
            # Commit changes
            if not dry_run:
                session.commit()
                logger.info("✅ Changes committed")
        
        logger.info("=" * 60)
        logger.info("Data cleanup complete!")
        logger.info(f"  Readings deleted: {stats['readings_deleted']}")
        logger.info(f"  Thermocouple readings deleted: {stats['thermocouple_readings_deleted']}")
        logger.info(f"  Events deleted: {stats['events_deleted']}")
        logger.info(f"  Alerts deleted: {stats['alerts_deleted']}")
        logger.info("=" * 60)
        
        return stats
    
    def cleanup_session_data(
        self,
        smoke_id: int,
        keep_last_n: int = 5000,
        dry_run: bool = False
    ) -> Tuple[int, int]:
        """
        Clean up excessive readings from a specific smoke session.
        Keeps the most recent N readings.
        
        Args:
            smoke_id: Smoke session ID
            keep_last_n: Number of most recent readings to keep
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (readings_deleted, tc_readings_deleted)
        """
        logger.info(f"Cleaning session {smoke_id} data (keeping last {keep_last_n} readings)")
        
        with get_session_sync() as session:
            # Get all reading IDs for this session, ordered by timestamp
            all_readings_query = select(Reading.id).where(
                Reading.smoke_id == smoke_id
            ).order_by(Reading.ts.desc())
            
            all_reading_ids = [r[0] for r in session.exec(all_readings_query).all()]
            
            if len(all_reading_ids) <= keep_last_n:
                logger.info(f"  Session has {len(all_reading_ids)} readings (within limit)")
                return 0, 0
            
            # IDs to delete (all except the last N)
            ids_to_delete = all_reading_ids[keep_last_n:]
            
            logger.info(f"  Found {len(ids_to_delete)} readings to delete")
            
            if dry_run:
                logger.info(f"  🔍 Would delete {len(ids_to_delete)} readings (dry run)")
                return len(ids_to_delete), 0
            
            # Delete thermocouple readings first
            tc_delete_stmt = delete(ThermocoupleReading).where(
                ThermocoupleReading.reading_id.in_(ids_to_delete)
            )
            tc_result = session.exec(tc_delete_stmt)
            tc_deleted = tc_result.rowcount
            
            # Delete readings
            reading_delete_stmt = delete(Reading).where(Reading.id.in_(ids_to_delete))
            reading_result = session.exec(reading_delete_stmt)
            reading_deleted = reading_result.rowcount
            
            session.commit()
            
            logger.info(f"  ✅ Deleted {reading_deleted} readings, {tc_deleted} TC readings")
            return reading_deleted, tc_deleted
    
    def get_database_stats(self) -> dict:
        """Get current database statistics."""
        with get_session_sync() as session:
            # Count records in each table
            reading_count = len(session.exec(select(Reading)).all())
            tc_reading_count = len(session.exec(select(ThermocoupleReading)).all())
            event_count = len(session.exec(select(Event)).all())
            alert_count = len(session.exec(select(Alert)).all())
            smoke_count = len(session.exec(select(Smoke)).all())
            
            # Get oldest and newest data
            oldest_reading = session.exec(
                select(Reading).order_by(Reading.ts).limit(1)
            ).first()
            newest_reading = session.exec(
                select(Reading).order_by(Reading.ts.desc()).limit(1)
            ).first()
            
            return {
                'readings': reading_count,
                'thermocouple_readings': tc_reading_count,
                'events': event_count,
                'alerts': alert_count,
                'smoke_sessions': smoke_count,
                'oldest_reading': oldest_reading.ts.isoformat() if oldest_reading else None,
                'newest_reading': newest_reading.ts.isoformat() if newest_reading else None,
            }


# Global instance
cleanup_manager = DataCleanupManager()

