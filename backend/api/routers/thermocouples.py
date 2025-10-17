"""Thermocouple API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db.models import Thermocouple
from db.session import get_session_sync
from core.controller import controller

router = APIRouter()


class ThermocoupleCreate(BaseModel):
    name: str
    cs_pin: int
    enabled: bool = True
    is_control: bool = False
    order: int = 0
    color: str = "#3b82f6"


class ThermocoupleUpdate(BaseModel):
    name: Optional[str] = None
    cs_pin: Optional[int] = None
    enabled: Optional[bool] = None
    is_control: Optional[bool] = None
    order: Optional[int] = None
    color: Optional[str] = None


@router.get("")
async def get_thermocouples():
    """Get all thermocouples."""
    try:
        with get_session_sync() as session:
            from sqlmodel import select
            statement = select(Thermocouple).order_by(Thermocouple.order)
            thermocouples = session.exec(statement).all()
            
            return {
                "thermocouples": [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "cs_pin": tc.cs_pin,
                        "enabled": tc.enabled,
                        "is_control": tc.is_control,
                        "order": tc.order,
                        "color": tc.color,
                        "created_at": tc.created_at.isoformat() + 'Z' if not tc.created_at.isoformat().endswith('Z') else tc.created_at.isoformat(),
                        "updated_at": tc.updated_at.isoformat() + 'Z' if not tc.updated_at.isoformat().endswith('Z') else tc.updated_at.isoformat()
                    }
                    for tc in thermocouples
                ],
                "count": len(thermocouples)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thermocouples: {str(e)}")


@router.get("/{thermocouple_id}")
async def get_thermocouple(thermocouple_id: int):
    """Get a specific thermocouple."""
    try:
        with get_session_sync() as session:
            tc = session.get(Thermocouple, thermocouple_id)
            if not tc:
                raise HTTPException(status_code=404, detail="Thermocouple not found")
            
            return {
                "id": tc.id,
                "name": tc.name,
                "cs_pin": tc.cs_pin,
                "enabled": tc.enabled,
                "is_control": tc.is_control,
                "order": tc.order,
                "color": tc.color,
                "created_at": tc.created_at.isoformat() + 'Z' if not tc.created_at.isoformat().endswith('Z') else tc.created_at.isoformat(),
                "updated_at": tc.updated_at.isoformat() + 'Z' if not tc.updated_at.isoformat().endswith('Z') else tc.updated_at.isoformat()
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get thermocouple: {str(e)}")


@router.post("")
async def create_thermocouple(tc_create: ThermocoupleCreate):
    """Create a new thermocouple."""
    try:
        with get_session_sync() as session:
            # If this is marked as control, unset other control thermocouples
            if tc_create.is_control:
                from sqlmodel import select
                statement = select(Thermocouple).where(Thermocouple.is_control == True)
                existing_control = session.exec(statement).all()
                for tc in existing_control:
                    tc.is_control = False
                session.commit()
            
            tc = Thermocouple(
                name=tc_create.name,
                cs_pin=tc_create.cs_pin,
                enabled=tc_create.enabled,
                is_control=tc_create.is_control,
                order=tc_create.order,
                color=tc_create.color
            )
            session.add(tc)
            session.commit()
            session.refresh(tc)
            
            # Reload thermocouples in controller
            controller.reload_thermocouples()
            
            return {
                "status": "success",
                "message": "Thermocouple created successfully",
                "thermocouple": {
                    "id": tc.id,
                    "name": tc.name,
                    "cs_pin": tc.cs_pin,
                    "enabled": tc.enabled,
                    "is_control": tc.is_control,
                    "order": tc.order,
                    "color": tc.color
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create thermocouple: {str(e)}")


@router.put("/{thermocouple_id}")
async def update_thermocouple(thermocouple_id: int, tc_update: ThermocoupleUpdate):
    """Update a thermocouple."""
    try:
        with get_session_sync() as session:
            tc = session.get(Thermocouple, thermocouple_id)
            if not tc:
                raise HTTPException(status_code=404, detail="Thermocouple not found")
            
            # If setting this as control, unset others
            if tc_update.is_control is True:
                from sqlmodel import select
                statement = select(Thermocouple).where(Thermocouple.is_control == True)
                existing_control = session.exec(statement).all()
                for existing_tc in existing_control:
                    if existing_tc.id != thermocouple_id:
                        existing_tc.is_control = False
                session.commit()
            
            # Update fields
            update_data = tc_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(tc, field, value)
            
            tc.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(tc)
            
            # Reload thermocouples in controller
            controller.reload_thermocouples()
            
            return {
                "status": "success",
                "message": "Thermocouple updated successfully",
                "thermocouple": {
                    "id": tc.id,
                    "name": tc.name,
                    "cs_pin": tc.cs_pin,
                    "enabled": tc.enabled,
                    "is_control": tc.is_control,
                    "order": tc.order,
                    "color": tc.color
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update thermocouple: {str(e)}")


@router.post("/{thermocouple_id}/set_control")
async def set_control_thermocouple(thermocouple_id: int):
    """Set a thermocouple as the control thermocouple."""
    try:
        with get_session_sync() as session:
            tc = session.get(Thermocouple, thermocouple_id)
            if not tc:
                raise HTTPException(status_code=404, detail="Thermocouple not found")
            
            # Unset all other control thermocouples
            from sqlmodel import select
            statement = select(Thermocouple).where(Thermocouple.is_control == True)
            existing_control = session.exec(statement).all()
            for existing_tc in existing_control:
                if existing_tc.id != thermocouple_id:
                    existing_tc.is_control = False
            
            # Set this one as control
            tc.is_control = True
            tc.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(tc)
            
            # Reload thermocouples in controller
            controller.reload_thermocouples()
            
            return {
                "status": "success",
                "message": f"Thermocouple '{tc.name}' set as control thermocouple",
                "thermocouple": {
                    "id": tc.id,
                    "name": tc.name,
                    "cs_pin": tc.cs_pin,
                    "enabled": tc.enabled,
                    "is_control": tc.is_control,
                    "order": tc.order,
                    "color": tc.color
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set control thermocouple: {str(e)}")


@router.delete("/{thermocouple_id}")
async def delete_thermocouple(thermocouple_id: int):
    """Delete a thermocouple."""
    try:
        with get_session_sync() as session:
            tc = session.get(Thermocouple, thermocouple_id)
            if not tc:
                raise HTTPException(status_code=404, detail="Thermocouple not found")
            
            # Can't delete if it's the only one
            from sqlmodel import select
            statement = select(Thermocouple)
            all_tcs = session.exec(statement).all()
            if len(all_tcs) <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete the only thermocouple. Create another one first."
                )
            
            # If deleting control thermocouple, set another as control
            if tc.is_control:
                statement = select(Thermocouple).where(Thermocouple.id != thermocouple_id)
                other_tcs = session.exec(statement).all()
                if other_tcs:
                    other_tcs[0].is_control = True
            
            session.delete(tc)
            session.commit()
            
            # Reload thermocouples in controller
            controller.reload_thermocouples()
            
            return {
                "status": "success",
                "message": "Thermocouple deleted successfully"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete thermocouple: {str(e)}")

