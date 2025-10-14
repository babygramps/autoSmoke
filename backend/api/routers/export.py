"""Export API endpoints."""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Response
from sqlmodel import select, and_, desc
import csv
import io

from db.models import Reading, Alert, Event
from db.session import get_session_sync

router = APIRouter()


@router.get("/readings.csv")
async def export_readings_csv(
    from_time: str = Query(..., description="Start time (ISO format)"),
    to_time: str = Query(..., description="End time (ISO format)"),
    format: str = Query("csv", description="Export format")
):
    """Export temperature readings as CSV."""
    try:
        # Parse time parameters
        try:
            from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format")
        
        with get_session_sync() as session:
            # Query readings
            query = select(Reading).where(
                and_(Reading.ts >= from_dt, Reading.ts <= to_dt)
            ).order_by(Reading.ts)
            
            readings = session.exec(query).all()
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "timestamp",
                "temp_c",
                "temp_f", 
                "setpoint_c",
                "setpoint_f",
                "output_bool",
                "relay_state",
                "loop_ms",
                "pid_output",
                "boost_active"
            ])
            
            # Write data
            for reading in readings:
                writer.writerow([
                    reading.ts.isoformat(),
                    reading.temp_c,
                    reading.temp_f,
                    reading.setpoint_c,
                    reading.setpoint_f,
                    reading.output_bool,
                    reading.relay_state,
                    reading.loop_ms,
                    reading.pid_output,
                    reading.boost_active
                ])
            
            # Return CSV response
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=readings_{from_dt.strftime('%Y%m%d_%H%M%S')}_to_{to_dt.strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export readings: {str(e)}")


@router.get("/alerts.csv")
async def export_alerts_csv(
    from_time: str = Query(..., description="Start time (ISO format)"),
    to_time: str = Query(..., description="End time (ISO format)")
):
    """Export alerts as CSV."""
    try:
        # Parse time parameters
        try:
            from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format")
        
        with get_session_sync() as session:
            # Query alerts
            query = select(Alert).where(
                and_(Alert.ts >= from_dt, Alert.ts <= to_dt)
            ).order_by(Alert.ts)
            
            alerts = session.exec(query).all()
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "timestamp",
                "alert_type",
                "severity",
                "message",
                "active",
                "acknowledged",
                "cleared_ts",
                "metadata"
            ])
            
            # Write data
            for alert in alerts:
                writer.writerow([
                    alert.ts.isoformat(),
                    alert.alert_type,
                    alert.severity,
                    alert.message,
                    alert.active,
                    alert.acknowledged,
                    alert.cleared_ts.isoformat() if alert.cleared_ts else "",
                    alert.metadata or ""
                ])
            
            # Return CSV response
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=alerts_{from_dt.strftime('%Y%m%d_%H%M%S')}_to_{to_dt.strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export alerts: {str(e)}")


@router.get("/events.csv")
async def export_events_csv(
    from_time: str = Query(..., description="Start time (ISO format)"),
    to_time: str = Query(..., description="End time (ISO format)")
):
    """Export system events as CSV."""
    try:
        # Parse time parameters
        try:
            from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format")
        
        with get_session_sync() as session:
            # Query events
            query = select(Event).where(
                and_(Event.ts >= from_dt, Event.ts <= to_dt)
            ).order_by(Event.ts)
            
            events = session.exec(query).all()
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "timestamp",
                "kind",
                "message",
                "meta_json"
            ])
            
            # Write data
            for event in events:
                writer.writerow([
                    event.ts.isoformat(),
                    event.kind,
                    event.message,
                    event.meta_json or ""
                ])
            
            # Return CSV response
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=events_{from_dt.strftime('%Y%m%d_%H%M%S')}_to_{to_dt.strftime('%Y%m%d_%H%M%S')}.csv"
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export events: {str(e)}")
