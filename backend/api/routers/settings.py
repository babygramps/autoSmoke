"""Settings API endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from db.models import Settings
from db.session import get_session_sync
from core.controller import controller
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class SettingsUpdate(BaseModel):
    units: Optional[str] = None
    setpoint_f: Optional[float] = None
    control_mode: Optional[str] = None
    kp: Optional[float] = None
    ki: Optional[float] = None
    kd: Optional[float] = None
    min_on_s: Optional[int] = None
    min_off_s: Optional[int] = None
    hyst_c: Optional[float] = None
    time_window_s: Optional[int] = None
    hi_alarm_c: Optional[float] = None
    lo_alarm_c: Optional[float] = None
    stuck_high_c: Optional[float] = None
    stuck_high_duration_s: Optional[int] = None
    sim_mode: Optional[bool] = None
    gpio_pin: Optional[int] = None
    relay_active_high: Optional[bool] = None
    boost_duration_s: Optional[int] = None
    webhook_url: Optional[str] = None


@router.get("")
async def get_settings():
    """Get current system settings."""
    try:
        with get_session_sync() as session:
            db_settings = session.get(Settings, 1)
            
            if not db_settings:
                # Create default settings
                db_settings = Settings()
                session.add(db_settings)
                session.commit()
                session.refresh(db_settings)
            
            return {
                "units": db_settings.units,
                "setpoint_c": db_settings.setpoint_c,
                "setpoint_f": db_settings.setpoint_f,
                "control_mode": db_settings.control_mode,
                "kp": db_settings.kp,
                "ki": db_settings.ki,
                "kd": db_settings.kd,
                "min_on_s": db_settings.min_on_s,
                "min_off_s": db_settings.min_off_s,
                "hyst_c": db_settings.hyst_c,
                "time_window_s": db_settings.time_window_s,
                "hi_alarm_c": db_settings.hi_alarm_c,
                "lo_alarm_c": db_settings.lo_alarm_c,
                "stuck_high_c": db_settings.stuck_high_c,
                "stuck_high_duration_s": db_settings.stuck_high_duration_s,
                "sim_mode": db_settings.sim_mode,
                "gpio_pin": db_settings.gpio_pin,
                "relay_active_high": db_settings.relay_active_high,
                "boost_duration_s": db_settings.boost_duration_s,
                "webhook_url": db_settings.webhook_url,
                "created_at": db_settings.created_at.isoformat(),
                "updated_at": db_settings.updated_at.isoformat()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("")
async def update_settings(settings_update: SettingsUpdate):
    """Update system settings."""
    try:
        with get_session_sync() as session:
            db_settings = session.get(Settings, 1)
            
            if not db_settings:
                db_settings = Settings()
                session.add(db_settings)
            
            # Update fields that were provided
            update_data = settings_update.dict(exclude_unset=True)
            
            for field, value in update_data.items():
                if hasattr(db_settings, field):
                    setattr(db_settings, field, value)
            
            # Update timestamp
            from datetime import datetime
            db_settings.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(db_settings)
            
            # Handle hardware setting changes (sim_mode, gpio_pin, relay_active_high)
            sim_mode_changed = settings_update.sim_mode is not None and settings_update.sim_mode != controller.sim_mode
            gpio_settings_changed = settings_update.gpio_pin is not None or settings_update.relay_active_high is not None
            
            if sim_mode_changed:
                # Sim mode change requires full hardware reload and controller must be stopped
                if controller.running:
                    logger.warning("Cannot change sim_mode while controller is running.")
                    logger.info("Database updated, but sim_mode will not change until controller is stopped and restarted.")
                else:
                    new_sim_mode = settings_update.sim_mode
                    new_gpio_pin = settings_update.gpio_pin if settings_update.gpio_pin is not None else db_settings.gpio_pin
                    new_relay_active_high = settings_update.relay_active_high if settings_update.relay_active_high is not None else db_settings.relay_active_high
                    
                    logger.info(f"Sim mode changed: sim_mode={new_sim_mode}, gpio_pin={new_gpio_pin}, active_high={new_relay_active_high}")
                    success = controller.reload_hardware(new_sim_mode, new_gpio_pin, new_relay_active_high)
                    if success:
                        logger.info("Hardware reloaded successfully with new sim_mode")
                    else:
                        logger.error("Failed to reload hardware")
            
            elif gpio_settings_changed:
                # GPIO settings can be updated on the fly (even when running)
                new_gpio_pin = settings_update.gpio_pin if settings_update.gpio_pin is not None else db_settings.gpio_pin
                new_relay_active_high = settings_update.relay_active_high if settings_update.relay_active_high is not None else db_settings.relay_active_high
                
                logger.info(f"GPIO settings changed: pin={new_gpio_pin}, active_high={new_relay_active_high}")
                success = controller.update_relay_settings(new_gpio_pin, new_relay_active_high)
                if success:
                    logger.info("✓ Relay GPIO settings updated successfully")
                else:
                    logger.warning("Failed to update relay GPIO settings - may need to restart controller")
            
            # Update controller settings (always update, not just when running)
            # Control mode - always update
            if settings_update.control_mode is not None:
                await controller.set_control_mode(settings_update.control_mode)
            
            # Timing parameters - always update
            if any(field in update_data for field in ['min_on_s', 'min_off_s', 'hyst_c', 'time_window_s']):
                min_on_s = settings_update.min_on_s or db_settings.min_on_s
                min_off_s = settings_update.min_off_s or db_settings.min_off_s
                hyst_c = settings_update.hyst_c or db_settings.hyst_c
                time_window_s = settings_update.time_window_s or db_settings.time_window_s
                await controller.set_timing_params(min_on_s, min_off_s, hyst_c, time_window_s)
            
            # These only matter when controller is running
            if controller.running:
                if settings_update.setpoint_f is not None:
                    # Check if there's an active session with phases - if so, don't override phase setpoint
                    if controller.active_smoke_id:
                        try:
                            from core.phase_manager import phase_manager
                            current_phase = phase_manager.get_current_phase(controller.active_smoke_id)
                            if current_phase:
                                logger.warning(f"Ignoring setpoint update - active phase controls setpoint: {current_phase.phase_name} @ {current_phase.target_temp_f}°F")
                                # Update DB but don't apply to controller
                            else:
                                # No active phase, safe to update
                                await controller.set_setpoint(settings_update.setpoint_f)
                        except Exception as e:
                            logger.warning(f"Error checking for active phase: {e}, applying setpoint update anyway")
                            await controller.set_setpoint(settings_update.setpoint_f)
                    else:
                        # No active session, safe to update
                        await controller.set_setpoint(settings_update.setpoint_f)
                
                if any(field in update_data for field in ['kp', 'ki', 'kd']):
                    kp = settings_update.kp or db_settings.kp
                    ki = settings_update.ki or db_settings.ki
                    kd = settings_update.kd or db_settings.kd
                    await controller.set_pid_gains(kp, ki, kd)
            
            return {
                "status": "success",
                "message": "Settings updated successfully",
                "settings": {
                    "units": db_settings.units,
                    "setpoint_c": db_settings.setpoint_c,
                    "setpoint_f": db_settings.setpoint_f,
                    "control_mode": db_settings.control_mode,
                    "kp": db_settings.kp,
                    "ki": db_settings.ki,
                    "kd": db_settings.kd,
                    "min_on_s": db_settings.min_on_s,
                    "min_off_s": db_settings.min_off_s,
                    "hyst_c": db_settings.hyst_c,
                    "time_window_s": db_settings.time_window_s,
                    "hi_alarm_c": db_settings.hi_alarm_c,
                    "lo_alarm_c": db_settings.lo_alarm_c,
                    "stuck_high_c": db_settings.stuck_high_c,
                    "stuck_high_duration_s": db_settings.stuck_high_duration_s,
                    "sim_mode": db_settings.sim_mode,
                    "gpio_pin": db_settings.gpio_pin,
                    "relay_active_high": db_settings.relay_active_high,
                    "boost_duration_s": db_settings.boost_duration_s,
                    "webhook_url": db_settings.webhook_url,
                    "updated_at": db_settings.updated_at.isoformat()
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/reset")
async def reset_settings():
    """Reset settings to defaults."""
    try:
        with get_session_sync() as session:
            db_settings = session.get(Settings, 1)
            
            if not db_settings:
                db_settings = Settings()
                session.add(db_settings)
            else:
                # Reset to defaults
                from db.models import CONTROL_MODE_THERMOSTAT
                db_settings.units = "F"
                db_settings.setpoint_c = 107.2  # 225°F
                db_settings.setpoint_f = 225.0
                db_settings.control_mode = CONTROL_MODE_THERMOSTAT
                db_settings.kp = 4.0
                db_settings.ki = 0.1
                db_settings.kd = 20.0
                db_settings.min_on_s = 5
                db_settings.min_off_s = 5
                db_settings.hyst_c = 0.6
                db_settings.time_window_s = 10
                db_settings.hi_alarm_c = 135.0
                db_settings.lo_alarm_c = 65.6
                db_settings.stuck_high_c = 2.0
                db_settings.stuck_high_duration_s = 60
                db_settings.sim_mode = False
                db_settings.gpio_pin = 17
                db_settings.relay_active_high = False
                db_settings.boost_duration_s = 60
                db_settings.webhook_url = None
                db_settings.updated_at = datetime.utcnow()
            
            session.commit()
            session.refresh(db_settings)
            
            return {
                "status": "success",
                "message": "Settings reset to defaults",
                "settings": {
                    "units": db_settings.units,
                    "setpoint_c": db_settings.setpoint_c,
                    "setpoint_f": db_settings.setpoint_f,
                    "control_mode": db_settings.control_mode,
                    "kp": db_settings.kp,
                    "ki": db_settings.ki,
                    "kd": db_settings.kd,
                    "min_on_s": db_settings.min_on_s,
                    "min_off_s": db_settings.min_off_s,
                    "hyst_c": db_settings.hyst_c,
                    "time_window_s": db_settings.time_window_s,
                    "hi_alarm_c": db_settings.hi_alarm_c,
                    "lo_alarm_c": db_settings.lo_alarm_c,
                    "stuck_high_c": db_settings.stuck_high_c,
                    "stuck_high_duration_s": db_settings.stuck_high_duration_s,
                    "sim_mode": db_settings.sim_mode,
                    "gpio_pin": db_settings.gpio_pin,
                    "relay_active_high": db_settings.relay_active_high,
                    "boost_duration_s": db_settings.boost_duration_s,
                    "webhook_url": db_settings.webhook_url,
                    "updated_at": db_settings.updated_at.isoformat()
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


@router.post("/test-webhook")
async def test_webhook():
    """Test webhook configuration by sending a test notification."""
    try:
        import httpx
        from datetime import datetime
        
        # Get current webhook URL from settings
        with get_session_sync() as session:
            db_settings = session.get(Settings, 1)
            webhook_url = db_settings.webhook_url if db_settings else None
        
        if not webhook_url:
            raise HTTPException(
                status_code=400,
                detail="No webhook URL configured. Please set a webhook URL in settings first."
            )
        
        # Create test payload
        test_payload = {
            "alert_id": 0,
            "alert_type": "test",
            "severity": "info",
            "message": "🧪 Test notification from PiTmaster Smoker Controller",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "test": True,
                "source": "settings_page",
                "note": "This is a test webhook to verify your configuration is working correctly"
            }
        }
        
        logger.info(f"Sending test webhook to: {webhook_url}")
        
        # Send webhook with timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=test_payload
            )
            response.raise_for_status()
        
        logger.info(f"Test webhook sent successfully. Status: {response.status_code}")
        
        return {
            "status": "success",
            "message": f"Test webhook sent successfully! Check your endpoint for the test notification.",
            "webhook_url": webhook_url,
            "status_code": response.status_code,
            "payload_sent": test_payload
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Webhook HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=500,
            detail=f"Webhook endpoint returned error {e.response.status_code}: {e.response.text[:200]}"
        )
    except httpx.RequestError as e:
        logger.error(f"Webhook request error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to webhook endpoint: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test webhook: {str(e)}")