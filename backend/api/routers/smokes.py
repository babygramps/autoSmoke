"""Smoke session management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db.models import Smoke
from db.session import get_session_sync
from core.controller import controller
from sqlmodel import select

router = APIRouter()


class SmokeCreate(BaseModel):
    name: str
    description: Optional[str] = None


class SmokeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_smokes(active_only: bool = False, limit: int = 50):
    """Get list of smoke sessions."""
    try:
        with get_session_sync() as session:
            if active_only:
                statement = select(Smoke).where(Smoke.is_active == True).limit(limit)
            else:
                statement = select(Smoke).order_by(Smoke.started_at.desc()).limit(limit)
            
            smokes = session.exec(statement).all()
            
            return {
                "smokes": [
                    {
                        "id": smoke.id,
                        "name": smoke.name,
                        "description": smoke.description,
                        "started_at": smoke.started_at.isoformat(),
                        "ended_at": smoke.ended_at.isoformat() if smoke.ended_at else None,
                        "is_active": smoke.is_active,
                        "total_duration_minutes": smoke.total_duration_minutes,
                        "avg_temp_f": smoke.avg_temp_f,
                        "min_temp_f": smoke.min_temp_f,
                        "max_temp_f": smoke.max_temp_f,
                    }
                    for smoke in smokes
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list smoke sessions: {str(e)}")


@router.get("/{smoke_id}")
async def get_smoke(smoke_id: int):
    """Get a specific smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            return {
                "id": smoke.id,
                "name": smoke.name,
                "description": smoke.description,
                "started_at": smoke.started_at.isoformat(),
                "ended_at": smoke.ended_at.isoformat() if smoke.ended_at else None,
                "is_active": smoke.is_active,
                "total_duration_minutes": smoke.total_duration_minutes,
                "avg_temp_f": smoke.avg_temp_f,
                "min_temp_f": smoke.min_temp_f,
                "max_temp_f": smoke.max_temp_f,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get smoke session: {str(e)}")


@router.post("")
async def create_smoke(smoke_create: SmokeCreate):
    """Create a new smoke session."""
    try:
        with get_session_sync() as session:
            # Deactivate all other smoke sessions
            statement = select(Smoke).where(Smoke.is_active == True)
            active_smokes = session.exec(statement).all()
            for active_smoke in active_smokes:
                active_smoke.is_active = False
                # Compute stats if ending a session
                if not active_smoke.ended_at:
                    active_smoke.ended_at = datetime.utcnow()
                    await _compute_smoke_stats(session, active_smoke)
            
            # Create new smoke session
            smoke = Smoke(
                name=smoke_create.name,
                description=smoke_create.description,
                is_active=True
            )
            session.add(smoke)
            session.commit()
            session.refresh(smoke)
            
            # Set as active in controller
            controller.set_active_smoke(smoke.id)
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' created",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "description": smoke.description,
                    "started_at": smoke.started_at.isoformat(),
                    "is_active": smoke.is_active
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create smoke session: {str(e)}")


@router.put("/{smoke_id}")
async def update_smoke(smoke_id: int, smoke_update: SmokeUpdate):
    """Update a smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            if smoke_update.name is not None:
                smoke.name = smoke_update.name
            if smoke_update.description is not None:
                smoke.description = smoke_update.description
            
            session.commit()
            session.refresh(smoke)
            
            return {
                "status": "success",
                "message": "Smoke session updated",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "description": smoke.description,
                    "started_at": smoke.started_at.isoformat(),
                    "ended_at": smoke.ended_at.isoformat() if smoke.ended_at else None,
                    "is_active": smoke.is_active
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update smoke session: {str(e)}")


@router.post("/{smoke_id}/activate")
async def activate_smoke(smoke_id: int):
    """Set a smoke session as active."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            # Deactivate all other smokes
            statement = select(Smoke).where(Smoke.is_active == True)
            active_smokes = session.exec(statement).all()
            for active_smoke in active_smokes:
                if active_smoke.id != smoke_id:
                    active_smoke.is_active = False
                    if not active_smoke.ended_at:
                        active_smoke.ended_at = datetime.utcnow()
                        await _compute_smoke_stats(session, active_smoke)
            
            # Activate this smoke
            smoke.is_active = True
            session.commit()
            
            # Set as active in controller
            controller.set_active_smoke(smoke.id)
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' activated"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate smoke session: {str(e)}")


@router.post("/{smoke_id}/end")
async def end_smoke(smoke_id: int):
    """End a smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            if smoke.ended_at:
                raise HTTPException(status_code=400, detail="Smoke session already ended")
            
            smoke.ended_at = datetime.utcnow()
            smoke.is_active = False
            
            # Compute statistics
            await _compute_smoke_stats(session, smoke)
            
            session.commit()
            
            # Clear active smoke in controller
            if controller.active_smoke_id == smoke_id:
                controller.active_smoke_id = None
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' ended",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "ended_at": smoke.ended_at.isoformat(),
                    "total_duration_minutes": smoke.total_duration_minutes,
                    "avg_temp_f": smoke.avg_temp_f,
                    "min_temp_f": smoke.min_temp_f,
                    "max_temp_f": smoke.max_temp_f,
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end smoke session: {str(e)}")


@router.delete("/{smoke_id}")
async def delete_smoke(smoke_id: int):
    """Delete a smoke session and all its readings."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            if smoke.is_active:
                raise HTTPException(status_code=400, detail="Cannot delete active smoke session. End it first.")
            
            # Delete associated readings
            from db.models import Reading
            statement = select(Reading).where(Reading.smoke_id == smoke_id)
            readings = session.exec(statement).all()
            for reading in readings:
                session.delete(reading)
            
            # Delete the smoke session
            session.delete(smoke)
            session.commit()
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' deleted"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete smoke session: {str(e)}")


async def _compute_smoke_stats(session, smoke: Smoke):
    """Compute statistics for a smoke session."""
    from db.models import Reading
    from sqlmodel import func, select
    
    # Duration
    if smoke.ended_at and smoke.started_at:
        duration = smoke.ended_at - smoke.started_at
        smoke.total_duration_minutes = int(duration.total_seconds() / 60)
    
    # Temperature stats
    statement = select(
        func.avg(Reading.temp_f),
        func.min(Reading.temp_f),
        func.max(Reading.temp_f)
    ).where(Reading.smoke_id == smoke.id)
    
    result = session.exec(statement).first()
    if result and result[0] is not None:
        smoke.avg_temp_f = round(result[0], 1)
        smoke.min_temp_f = round(result[1], 1)
        smoke.max_temp_f = round(result[2], 1)

