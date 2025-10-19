"""Database maintenance API endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from core.data_cleanup import cleanup_manager
from core.db_maintenance import db_maintenance

logger = logging.getLogger(__name__)

router = APIRouter()


class CleanupRequest(BaseModel):
    """Request model for data cleanup."""
    reading_days: Optional[int] = 30
    event_days: Optional[int] = 90
    alert_days: Optional[int] = 60
    dry_run: bool = True  # Default to dry run for safety


@router.get("/stats")
async def get_database_stats():
    """Get database statistics and health information."""
    try:
        # Get data statistics
        data_stats = cleanup_manager.get_database_stats()
        
        # Get database info
        db_info = db_maintenance.get_database_info()
        
        return {
            "status": "success",
            "data": {
                **data_stats,
                "database": db_info
            }
        }
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_data(request: CleanupRequest):
    """Clean up old data from the database."""
    try:
        logger.info(f"Starting data cleanup (dry_run={request.dry_run})")
        
        stats = cleanup_manager.cleanup_old_data(
            reading_days=request.reading_days,
            event_days=request.event_days,
            alert_days=request.alert_days,
            dry_run=request.dry_run
        )
        
        # Run vacuum if actual deletion occurred
        if not request.dry_run and (stats['readings_deleted'] > 0 or stats['events_deleted'] > 0):
            logger.info("Running VACUUM after cleanup...")
            db_maintenance.vacuum()
        
        return {
            "status": "success",
            "message": "Data cleanup completed" if not request.dry_run else "Dry run completed (no data deleted)",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=f"Data cleanup failed: {str(e)}")


@router.post("/vacuum")
async def vacuum_database():
    """Run VACUUM on the database to reclaim space."""
    try:
        logger.info("Running VACUUM via API")
        success = db_maintenance.vacuum()
        
        if success:
            return {
                "status": "success",
                "message": "Database VACUUM completed successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="VACUUM failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VACUUM failed: {e}")
        raise HTTPException(status_code=500, detail=f"VACUUM failed: {str(e)}")


@router.post("/analyze")
async def analyze_database():
    """Run ANALYZE to update query planner statistics."""
    try:
        logger.info("Running ANALYZE via API")
        success = db_maintenance.analyze()
        
        if success:
            return {
                "status": "success",
                "message": "Database ANALYZE completed successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="ANALYZE failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ANALYZE failed: {e}")
        raise HTTPException(status_code=500, detail=f"ANALYZE failed: {str(e)}")


@router.post("/optimize")
async def optimize_database():
    """Run full database optimization (ANALYZE + VACUUM + optimization pragmas)."""
    try:
        logger.info("Running full database optimization via API")
        results = db_maintenance.full_maintenance()
        
        all_success = all(results.values())
        
        return {
            "status": "success" if all_success else "partial",
            "message": "Database optimization completed" if all_success else "Some optimization steps failed",
            "results": results
        }
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Database optimization failed: {str(e)}")


@router.get("/health")
async def database_health():
    """Get database health metrics and recommendations."""
    try:
        db_info = db_maintenance.get_database_info()
        data_stats = cleanup_manager.get_database_stats()
        
        # Determine health status and recommendations
        recommendations = []
        health_status = "good"
        
        # Check fragmentation
        if db_info.get('fragmentation_pct', 0) > 20:
            recommendations.append({
                "severity": "warning",
                "message": f"Database fragmentation is high ({db_info['fragmentation_pct']}%). Consider running VACUUM.",
                "action": "vacuum"
            })
            health_status = "warning"
        
        if db_info.get('fragmentation_pct', 0) > 40:
            recommendations.append({
                "severity": "critical",
                "message": f"Database fragmentation is critical ({db_info['fragmentation_pct']}%). Run VACUUM immediately.",
                "action": "vacuum"
            })
            health_status = "critical"
        
        # Check reading count
        reading_count = data_stats.get('readings', 0)
        if reading_count > 100000:
            recommendations.append({
                "severity": "warning",
                "message": f"Large number of readings ({reading_count:,}). Consider cleanup to improve performance.",
                "action": "cleanup"
            })
            if health_status == "good":
                health_status = "warning"
        
        if reading_count > 200000:
            recommendations.append({
                "severity": "critical",
                "message": f"Very large number of readings ({reading_count:,}). Performance may be degraded.",
                "action": "cleanup"
            })
            health_status = "critical"
        
        # Check database size
        total_size_mb = db_info.get('total_size_mb', 0)
        if total_size_mb > 500:
            recommendations.append({
                "severity": "info",
                "message": f"Database size is {total_size_mb} MB. Consider cleanup if disk space is limited.",
                "action": "cleanup"
            })
        
        # Check journal mode
        if db_info.get('journal_mode', '').upper() != 'WAL':
            recommendations.append({
                "severity": "info",
                "message": "Database is not using WAL mode. Run optimization for better performance.",
                "action": "optimize"
            })
        
        return {
            "status": "success",
            "health_status": health_status,
            "database_size_mb": total_size_mb,
            "fragmentation_pct": db_info.get('fragmentation_pct', 0),
            "total_readings": reading_count,
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Failed to get database health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database health: {str(e)}")
