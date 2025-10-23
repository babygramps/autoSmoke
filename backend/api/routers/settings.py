"""Settings API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Annotated, Optional

from core.container import get_controller, get_settings_repository
from core.controller import SmokerController
from core.config import settings
from db.repositories import SettingsRepository

logger = logging.getLogger(__name__)

ControllerDep = Annotated[SmokerController, Depends(get_controller)]
SettingsRepoDep = Annotated[SettingsRepository, Depends(get_settings_repository)]

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


def _serialize_settings(db_settings) -> dict:
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
        "updated_at": db_settings.updated_at.isoformat(),
    }


@router.get("")
async def get_settings(settings_repo: SettingsRepoDep):
    """Get current system settings."""
    try:
        db_settings = await settings_repo.get_settings_async(ensure=True)
        if not db_settings:
            raise HTTPException(status_code=500, detail="Failed to load settings")
        return _serialize_settings(db_settings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")


@router.put("")
async def update_settings(
    settings_update: SettingsUpdate,
    controller: ControllerDep,
    settings_repo: SettingsRepoDep,
):
    """Update system settings."""
    try:
        current_settings = await settings_repo.get_settings_async(ensure=True)
        if not current_settings:
            raise HTTPException(status_code=500, detail="Failed to load settings")

        update_data = settings_update.dict(exclude_unset=True)
        updated_settings = current_settings
        if update_data:
            updated_settings = await settings_repo.update_settings_async(update_data)

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
                new_gpio_pin = (
                    settings_update.gpio_pin
                    if settings_update.gpio_pin is not None
                    else updated_settings.gpio_pin
                )
                new_relay_active_high = (
                    settings_update.relay_active_high
                    if settings_update.relay_active_high is not None
                    else updated_settings.relay_active_high
                )

                logger.info(
                    "Sim mode changed: sim_mode=%s, gpio_pin=%s, active_high=%s",
                    new_sim_mode,
                    new_gpio_pin,
                    new_relay_active_high,
                )
                success = controller.reload_hardware(new_sim_mode, new_gpio_pin, new_relay_active_high)
                if success:
                    logger.info("Hardware reloaded successfully with new sim_mode")
                else:
                    logger.error("Failed to reload hardware")

        elif gpio_settings_changed:
            # GPIO settings can be updated on the fly (even when running)
            new_gpio_pin = (
                settings_update.gpio_pin
                if settings_update.gpio_pin is not None
                else updated_settings.gpio_pin
            )
            new_relay_active_high = (
                settings_update.relay_active_high
                if settings_update.relay_active_high is not None
                else updated_settings.relay_active_high
            )

            logger.info(
                "GPIO settings changed: pin=%s, active_high=%s",
                new_gpio_pin,
                new_relay_active_high,
            )
            success = controller.update_relay_settings(new_gpio_pin, new_relay_active_high)
            if success:
                logger.info("✓ Relay GPIO settings updated successfully")
            else:
                logger.warning("Failed to update relay GPIO settings - may need to restart controller")

        # Update controller settings (always update, not just when running)
        if settings_update.control_mode is not None:
            await controller.set_control_mode(settings_update.control_mode)

        if any(field in update_data for field in ['min_on_s', 'min_off_s', 'hyst_c', 'time_window_s']):
            min_on_s = (
                settings_update.min_on_s
                if settings_update.min_on_s is not None
                else updated_settings.min_on_s
            )
            min_off_s = (
                settings_update.min_off_s
                if settings_update.min_off_s is not None
                else updated_settings.min_off_s
            )
            hyst_c = (
                settings_update.hyst_c
                if settings_update.hyst_c is not None
                else updated_settings.hyst_c
            )
            time_window_s = (
                settings_update.time_window_s
                if settings_update.time_window_s is not None
                else updated_settings.time_window_s
            )
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
                            logger.warning(
                                "Ignoring setpoint update - active phase controls setpoint: %s @ %s°F",
                                current_phase.phase_name,
                                current_phase.target_temp_f,
                            )
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
                kp = settings_update.kp if settings_update.kp is not None else updated_settings.kp
                ki = settings_update.ki if settings_update.ki is not None else updated_settings.ki
                kd = settings_update.kd if settings_update.kd is not None else updated_settings.kd
                await controller.set_pid_gains(kp, ki, kd)

        return {
            "status": "success",
            "message": "Settings updated successfully",
            "settings": _serialize_settings(updated_settings),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")


@router.post("/reset")
async def reset_settings(settings_repo: SettingsRepoDep):
    """Reset settings to defaults."""
    try:
        db_settings = await settings_repo.reset_settings_async()
        return {
            "status": "success",
            "message": "Settings reset to defaults",
            "settings": _serialize_settings(db_settings),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


@router.post("/test-webhook")
async def test_webhook(settings_repo: SettingsRepoDep):
    """Test webhook configuration by sending a test notification."""
    try:
        import httpx
        from datetime import datetime
        
        # Get current webhook URL from settings
        webhook_url = await settings_repo.get_webhook_url_async()

        if not webhook_url:
            raise HTTPException(
                status_code=400,
                detail="No webhook URL configured. Please set a webhook URL in settings first."
            )
        
        # Detect Discord webhook and format accordingly
        is_discord = "discord.com/api/webhooks" in webhook_url.lower()
        
        if is_discord:
            # Discord-specific format with rich embed
            test_payload = {
                "username": "PiTmaster Smoker",
                "avatar_url": "https://raw.githubusercontent.com/discord/discord-api-docs/main/images/robot.png",
                "embeds": [{
                    "title": "🧪 Test Notification",
                    "description": "This is a test webhook from your PiTmaster Smoker Controller!",
                    "color": 3447003,  # Blue color
                    "fields": [
                        {
                            "name": "Status",
                            "value": "✅ Webhook configuration is working correctly",
                            "inline": False
                        },
                        {
                            "name": "Test Type",
                            "value": "Manual test from Settings page",
                            "inline": True
                        },
                        {
                            "name": "Alert Type",
                            "value": "test",
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "Real alerts will include temperature data and severity levels"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
        else:
            # Generic format for other webhooks (IFTTT, Home Assistant, etc.)
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
        
        logger.info(f"Sending test webhook to: {webhook_url} (Discord: {is_discord})")
        
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
            "message": f"Test webhook sent successfully! Check your {'Discord server' if is_discord else 'endpoint'} for the test notification.",
            "webhook_url": webhook_url,
            "webhook_type": "Discord" if is_discord else "Generic",
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