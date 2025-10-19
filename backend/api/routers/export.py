"""Export API endpoints."""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Response
from sqlmodel import select, and_, desc
import csv
import io
import logging
from typing import Dict, List

from db.models import Reading, Alert, Event, Thermocouple, ThermocoupleReading
from db.session import get_session_sync

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/readings.csv")
async def export_readings_csv(
    from_time: str = Query(..., description="Start time (ISO format)"),
    to_time: str = Query(..., description="End time (ISO format)"),
    format: str = Query("csv", description="Export format")
):
    """Export temperature readings as CSV with all thermocouple data."""
    try:
        # Parse time parameters
        try:
            from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format")
        
        logger.info(f"📥 Exporting readings from {from_dt} to {to_dt}")
        
        with get_session_sync() as session:
            # Query readings
            query = select(Reading).where(
                and_(Reading.ts >= from_dt, Reading.ts <= to_dt)
            ).order_by(Reading.ts)
            
            readings = session.exec(query).all()
            logger.info(f"📊 Found {len(readings)} readings to export")
            
            if not readings:
                logger.warning("⚠ No readings found in specified time range")
            
            # Get all thermocouples (ordered by display order)
            thermocouples_query = select(Thermocouple).order_by(Thermocouple.order)
            thermocouples = session.exec(thermocouples_query).all()
            logger.info(f"🌡️ Found {len(thermocouples)} configured thermocouples")
            
            # Build thermocouple ID -> name mapping
            tc_map: Dict[int, Thermocouple] = {tc.id: tc for tc in thermocouples}
            
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Build dynamic header with thermocouple columns
            header = [
                "timestamp",
                "smoke_id",
                "control_temp_c",
                "control_temp_f", 
                "setpoint_c",
                "setpoint_f",
                "output_bool",
                "relay_state",
                "loop_ms",
                "pid_output",
                "boost_active"
            ]
            
            # Add columns for each thermocouple (temp_c, temp_f, fault)
            for tc in thermocouples:
                header.append(f"tc_{tc.id}_{tc.name.replace(' ', '_')}_temp_c")
                header.append(f"tc_{tc.id}_{tc.name.replace(' ', '_')}_temp_f")
                header.append(f"tc_{tc.id}_{tc.name.replace(' ', '_')}_fault")
            
            writer.writerow(header)
            logger.debug(f"📝 CSV header: {header}")
            
            # Write data rows
            for reading in readings:
                # Start with main reading data
                row = [
                    reading.ts.isoformat(),
                    reading.smoke_id or "",
                    reading.temp_c,
                    reading.temp_f,
                    reading.setpoint_c,
                    reading.setpoint_f,
                    reading.output_bool,
                    reading.relay_state,
                    reading.loop_ms,
                    reading.pid_output,
                    reading.boost_active
                ]
                
                # Query thermocouple readings for this reading
                tc_readings_query = select(ThermocoupleReading).where(
                    ThermocoupleReading.reading_id == reading.id
                )
                tc_readings = session.exec(tc_readings_query).all()
                
                # Build map of thermocouple_id -> reading data
                tc_data_map: Dict[int, ThermocoupleReading] = {
                    tc_reading.thermocouple_id: tc_reading 
                    for tc_reading in tc_readings
                }
                
                # Add thermocouple data in the same order as header
                for tc in thermocouples:
                    if tc.id in tc_data_map:
                        tc_reading = tc_data_map[tc.id]
                        row.append(tc_reading.temp_c)
                        row.append(tc_reading.temp_f)
                        row.append(tc_reading.fault)
                    else:
                        # No data for this thermocouple at this timestamp
                        row.append("")
                        row.append("")
                        row.append("")
                
                writer.writerow(row)
            
            # Return CSV response
            csv_content = output.getvalue()
            output.close()
            
            logger.info(f"✅ CSV export complete: {len(readings)} readings exported")
            
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
        logger.error(f"❌ Failed to export readings: {e}", exc_info=True)
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
