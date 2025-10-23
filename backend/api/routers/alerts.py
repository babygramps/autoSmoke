"""Alerts API endpoints."""

from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, desc

from db.models import Alert
from db.session import get_session_sync
from core.alerts import AlertManager
from core.container import get_alert_manager

AlertManagerDep = Annotated[AlertManager, Depends(get_alert_manager)]

router = APIRouter()


@router.get("")
async def get_alerts(
    active_only: bool = Query(True, description="Only return active alerts"),
    limit: int = Query(100, description="Maximum number of alerts", le=1000)
):
    """Get system alerts."""
    try:
        with get_session_sync() as session:
            query = select(Alert)
            
            if active_only:
                query = query.where(Alert.active == True)
            
            query = query.order_by(desc(Alert.ts)).limit(limit)
            alerts = session.exec(query).all()
            
            return {
                "alerts": [
                    {
                        "id": alert.id,
                        "ts": alert.ts.isoformat() + 'Z' if not alert.ts.isoformat().endswith('Z') else alert.ts.isoformat(),
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "active": alert.active,
                        "acknowledged": alert.acknowledged,
                        "cleared_ts": (alert.cleared_ts.isoformat() + 'Z' if not alert.cleared_ts.isoformat().endswith('Z') else alert.cleared_ts.isoformat()) if alert.cleared_ts else None,
                        "metadata": alert.meta_data
                    }
                    for alert in alerts
                ],
                "count": len(alerts),
                "active_only": active_only
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")


@router.get("/summary")
async def get_alert_summary(alert_manager: AlertManagerDep):
    """Get alert summary statistics."""
    try:
        summary = await alert_manager.get_alert_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert summary: {str(e)}")


@router.post("/{alert_id}/ack")
async def acknowledge_alert(alert_id: int, alert_manager: AlertManagerDep):
    """Acknowledge an alert."""
    try:
        success = await alert_manager.acknowledge_alert(alert_id)
        
        if success:
            return {"status": "success", "message": f"Alert {alert_id} acknowledged"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or not active")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to acknowledge alert: {str(e)}")


@router.post("/{alert_id}/clear")
async def clear_alert(alert_id: int, alert_manager: AlertManagerDep):
    """Manually clear an alert."""
    try:
        success = await alert_manager.clear_alert(alert_id)
        
        if success:
            return {"status": "success", "message": f"Alert {alert_id} cleared"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or not active")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear alert: {str(e)}")


@router.post("/clear-all")
async def clear_all_alerts(alert_manager: AlertManagerDep):
    """Clear all active alerts."""
    try:
        with get_session_sync() as session:
            # Get all active alerts
            query = select(Alert).where(Alert.active == True)
            active_alerts = session.exec(query).all()
            
            cleared_count = 0
            for alert in active_alerts:
                success = await alert_manager.clear_alert(alert.id)
                if success:
                    cleared_count += 1
            
            return {
                "status": "success",
                "message": f"Cleared {cleared_count} alerts",
                "cleared_count": cleared_count
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear all alerts: {str(e)}")


@router.get("/{alert_id}")
async def get_alert(alert_id: int):
    """Get a specific alert by ID."""
    try:
        with get_session_sync() as session:
            alert = session.get(Alert, alert_id)
            
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            return {
                "id": alert.id,
                "ts": alert.ts.isoformat(),
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "active": alert.active,
                "acknowledged": alert.acknowledged,
                "cleared_ts": alert.cleared_ts.isoformat() if alert.cleared_ts else None,
                "metadata": alert.meta_data
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alert: {str(e)}")
