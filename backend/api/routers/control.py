"""Control API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from core.controller import controller
from core.alerts import alert_manager
from core.config import settings
from db.models import Settings as DBSettings
from db.session import get_session_sync

router = APIRouter()


class SetpointRequest(BaseModel):
    value: float
    units: str = "F"


class PIDGainsRequest(BaseModel):
    kp: float
    ki: float
    kd: float
    min_on_s: int
    min_off_s: int
    hyst_c: float


class BoostRequest(BaseModel):
    duration_s: Optional[int] = None


@router.post("/start")
async def start_controller():
    """Start the smoker controller."""
    try:
        await controller.start()
        return {"status": "started", "message": "Controller started successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start controller: {str(e)}")


@router.post("/stop")
async def stop_controller():
    """Stop the smoker controller."""
    try:
        await controller.stop()
        return {"status": "stopped", "message": "Controller stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop controller: {str(e)}")


@router.get("/status")
async def get_status():
    """Get current controller status."""
    try:
        status = controller.get_status()
        alert_summary = await alert_manager.get_alert_summary()
        status["alert_summary"] = alert_summary
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/setpoint")
async def set_setpoint(request: SetpointRequest):
    """Set temperature setpoint."""
    try:
        if request.units.upper() not in ["F", "C"]:
            raise HTTPException(status_code=400, detail="Units must be 'F' or 'C'")
        
        if request.units.upper() == "C":
            setpoint_f = settings.celsius_to_fahrenheit(request.value)
        else:
            setpoint_f = request.value
        
        setpoint_c = settings.fahrenheit_to_celsius(setpoint_f)
        
        # Update controller
        await controller.set_setpoint(setpoint_f)
        
        # Persist to database
        with get_session_sync() as session:
            db_settings = session.get(DBSettings, 1)
            if not db_settings:
                db_settings = DBSettings()
                session.add(db_settings)
            
            db_settings.setpoint_f = setpoint_f
            db_settings.setpoint_c = setpoint_c
            db_settings.updated_at = datetime.utcnow()
            
            session.commit()
        
        return {
            "status": "success",
            "message": f"Setpoint updated to {setpoint_f:.1f}°F",
            "setpoint_f": setpoint_f,
            "setpoint_c": setpoint_c
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set setpoint: {str(e)}")


@router.post("/pid")
async def set_pid_gains(request: PIDGainsRequest):
    """Update PID gains and timing parameters."""
    try:
        # Validate parameters
        if request.kp < 0 or request.ki < 0 or request.kd < 0:
            raise HTTPException(status_code=400, detail="PID gains must be non-negative")
        
        if request.min_on_s < 0 or request.min_off_s < 0:
            raise HTTPException(status_code=400, detail="Minimum times must be non-negative")
        
        if request.hyst_c < 0:
            raise HTTPException(status_code=400, detail="Hysteresis must be non-negative")
        
        await controller.set_pid_gains(request.kp, request.ki, request.kd)
        await controller.set_timing_params(request.min_on_s, request.min_off_s, request.hyst_c)
        
        return {
            "status": "success",
            "message": "PID parameters updated successfully",
            "kp": request.kp,
            "ki": request.ki,
            "kd": request.kd,
            "min_on_s": request.min_on_s,
            "min_off_s": request.min_off_s,
            "hyst_c": request.hyst_c
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update PID parameters: {str(e)}")


@router.post("/boost")
async def enable_boost(request: BoostRequest):
    """Enable boost mode."""
    try:
        duration = request.duration_s or settings.smoker_boost_duration_s
        await controller.enable_boost(duration)
        return {
            "status": "success",
            "message": f"Boost mode enabled for {duration} seconds",
            "duration_s": duration
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enable boost: {str(e)}")


@router.delete("/boost")
async def disable_boost():
    """Disable boost mode."""
    try:
        await controller.disable_boost()
        return {"status": "success", "message": "Boost mode disabled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disable boost: {str(e)}")
