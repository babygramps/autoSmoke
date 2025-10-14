"""Readings API endpoints."""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from sqlmodel import select, and_, desc

from db.models import Reading
from db.session import get_session_sync
from core.controller import controller

router = APIRouter()


@router.get("")
async def get_readings(
    smoke_id: Optional[int] = Query(None, description="Filter by smoke session ID"),
    from_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    to_time: Optional[str] = Query(None, description="End time (ISO format)"),
    limit: int = Query(1000, description="Maximum number of readings", le=10000)
):
    """Get temperature readings with optional filtering."""
    try:
        with get_session_sync() as session:
            # Build query
            query = select(Reading)
            
            # Filter by smoke session if provided
            if smoke_id is not None:
                query = query.where(Reading.smoke_id == smoke_id)
            
            # Apply time filters
            if from_time:
                try:
                    from_dt = datetime.fromisoformat(from_time.replace('Z', '+00:00'))
                    query = query.where(Reading.ts >= from_dt)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid from_time format")
            
            if to_time:
                try:
                    to_dt = datetime.fromisoformat(to_time.replace('Z', '+00:00'))
                    query = query.where(Reading.ts <= to_dt)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid to_time format")
            
            # Apply limit and ordering
            query = query.order_by(desc(Reading.ts)).limit(limit)
            
            # Execute query
            readings = session.exec(query).all()
            
            return {
                "readings": [
                    {
                        "id": r.id,
                        "ts": r.ts.isoformat(),
                        "smoke_id": r.smoke_id,
                        "temp_c": r.temp_c,
                        "temp_f": r.temp_f,
                        "setpoint_c": r.setpoint_c,
                        "setpoint_f": r.setpoint_f,
                        "output_bool": r.output_bool,
                        "relay_state": r.relay_state,
                        "loop_ms": r.loop_ms,
                        "pid_output": r.pid_output,
                        "boost_active": r.boost_active
                    }
                    for r in readings
                ],
                "count": len(readings),
                "limit": limit
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get readings: {str(e)}")


@router.get("/latest")
async def get_latest_reading(
    smoke_id: Optional[int] = Query(None, description="Filter by smoke session ID")
):
    """Get the most recent reading."""
    try:
        with get_session_sync() as session:
            query = select(Reading)
            if smoke_id is not None:
                query = query.where(Reading.smoke_id == smoke_id)
            query = query.order_by(desc(Reading.ts)).limit(1)
            reading = session.exec(query).first()
            
            if not reading:
                return {"reading": None}
            
            return {
                "reading": {
                    "id": reading.id,
                    "ts": reading.ts.isoformat(),
                    "temp_c": reading.temp_c,
                    "temp_f": reading.temp_f,
                    "setpoint_c": reading.setpoint_c,
                    "setpoint_f": reading.setpoint_f,
                    "output_bool": reading.output_bool,
                    "relay_state": reading.relay_state,
                    "loop_ms": reading.loop_ms,
                    "pid_output": reading.pid_output,
                    "boost_active": reading.boost_active
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest reading: {str(e)}")


@router.get("/stats")
async def get_reading_stats(
    smoke_id: Optional[int] = Query(None, description="Filter by smoke session ID"),
    hours: int = Query(24, description="Number of hours to analyze", le=168)  # Max 1 week
):
    """Get reading statistics for the specified time period."""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        with get_session_sync() as session:
            conditions = [Reading.ts >= start_time, Reading.ts <= end_time]
            if smoke_id is not None:
                conditions.append(Reading.smoke_id == smoke_id)
            
            query = select(Reading).where(and_(*conditions))
            readings = session.exec(query).all()
            
            if not readings:
                return {
                    "period_hours": hours,
                    "reading_count": 0,
                    "stats": None
                }
            
            temps_c = [r.temp_c for r in readings if r.temp_c is not None]
            temps_f = [r.temp_f for r in readings if r.temp_f is not None]
            
            if not temps_c:
                return {
                    "period_hours": hours,
                    "reading_count": len(readings),
                    "stats": None
                }
            
            # Calculate statistics
            min_temp_c = min(temps_c)
            max_temp_c = max(temps_c)
            avg_temp_c = sum(temps_c) / len(temps_c)
            
            min_temp_f = min(temps_f)
            max_temp_f = max(temps_f)
            avg_temp_f = sum(temps_f) / len(temps_f)
            
            # Calculate relay on time percentage
            relay_on_count = sum(1 for r in readings if r.relay_state)
            relay_on_percentage = (relay_on_count / len(readings)) * 100 if readings else 0
            
            return {
                "period_hours": hours,
                "reading_count": len(readings),
                "stats": {
                    "temperature_c": {
                        "min": round(min_temp_c, 1),
                        "max": round(max_temp_c, 1),
                        "avg": round(avg_temp_c, 1)
                    },
                    "temperature_f": {
                        "min": round(min_temp_f, 1),
                        "max": round(max_temp_f, 1),
                        "avg": round(avg_temp_f, 1)
                    },
                    "relay_on_percentage": round(relay_on_percentage, 1)
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reading stats: {str(e)}")
