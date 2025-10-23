"""Alert system with debouncing and webhook support."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx
from core.config import settings
from db.models import Alert, Event
from db.session import get_session_sync

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages system alerts with debouncing and webhook notifications."""
    
    def __init__(self):
        self.active_alerts: Dict[str, int] = {}  # alert_key -> alert_id
        self.alert_conditions: Dict[str, Dict] = {}
        self.webhook_client = httpx.AsyncClient(timeout=10.0)
        
        # Debounce timers
        self.debounce_timers: Dict[str, datetime] = {}
        self.debounce_duration = timedelta(seconds=5)  # 5 second debounce
        
        # Rate limiting for webhooks
        self.last_webhook_time = None
        self.webhook_rate_limit = timedelta(minutes=1)  # Max 1 webhook per minute
        
        logger.info("AlertManager initialized")
    
    async def check_alerts(self, controller_status: dict):
        """Check all alert conditions and manage alerts."""
        try:
            # High temperature alert
            await self._check_high_temp_alert(controller_status)
            
            # Low temperature alert
            await self._check_low_temp_alert(controller_status)
            
            # Stuck high temperature alert
            await self._check_stuck_high_alert(controller_status)
            
            # Sensor fault alert
            await self._check_sensor_fault_alert(controller_status)
            
            # Hardware fallback alert
            await self._check_hardware_fallback_alert(controller_status)
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    async def _check_high_temp_alert(self, status: dict):
        """Check for high temperature alert."""
        temp_c = status.get("current_temp_c")
        if temp_c is None:
            return
        
        alert_key = "high_temp"
        
        # Get threshold from database settings
        try:
            from db.models import Settings as DBSettings
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                threshold = db_settings.hi_alarm_c if db_settings else settings.smoker_hi_alarm_c
        except Exception as e:
            logger.error(f"Failed to load alarm threshold from DB: {e}")
            threshold = settings.smoker_hi_alarm_c
        
        if temp_c >= threshold:
            if alert_key not in self.active_alerts:
                await self._create_alert(
                    alert_key,
                    "high_temp",
                    "error",
                    f"High temperature alert: {temp_c:.1f}°C (threshold: {threshold:.1f}°C)",
                    {"temp_c": temp_c, "threshold": threshold}
                )
        else:
            await self._clear_alert(alert_key, "Temperature returned to normal range")
    
    async def _check_low_temp_alert(self, status: dict):
        """Check for low temperature alert."""
        temp_c = status.get("current_temp_c")
        if temp_c is None:
            return
        
        alert_key = "low_temp"
        
        # Get threshold from database settings
        try:
            from db.models import Settings as DBSettings
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                threshold = db_settings.lo_alarm_c if db_settings else settings.smoker_lo_alarm_c
        except Exception as e:
            logger.error(f"Failed to load alarm threshold from DB: {e}")
            threshold = settings.smoker_lo_alarm_c
        
        if temp_c <= threshold:
            if alert_key not in self.active_alerts:
                await self._create_alert(
                    alert_key,
                    "low_temp",
                    "warning",
                    f"Low temperature alert: {temp_c:.1f}°C (threshold: {threshold:.1f}°C)",
                    {"temp_c": temp_c, "threshold": threshold}
                )
        else:
            await self._clear_alert(alert_key, "Temperature returned to normal range")
    
    async def _check_stuck_high_alert(self, status: dict):
        """Check for stuck high temperature alert (relay off but temp rising)."""
        temp_c = status.get("current_temp_c")
        relay_state = status.get("relay_state", False)
        
        if temp_c is None:
            return
        
        alert_key = "stuck_high"
        
        # Track temperature history for stuck high detection
        if not hasattr(self, '_temp_history'):
            self._temp_history = []
        
        now = datetime.utcnow()
        self._temp_history.append((now, temp_c))
        
        # Keep only last 2 minutes of history
        cutoff = now - timedelta(minutes=2)
        self._temp_history = [(t, temp) for t, temp in self._temp_history if t > cutoff]
        
        # Check if relay is off but temperature is rising
        if not relay_state and len(self._temp_history) >= 2:
            # Calculate temperature rate
            recent_temps = [temp for t, temp in self._temp_history[-10:]]  # Last 10 readings
            if len(recent_temps) >= 2:
                temp_rate = (recent_temps[-1] - recent_temps[0]) / len(recent_temps)  # °C per reading
                temp_rate_per_min = temp_rate * 60  # Convert to °C per minute
                
                # Get threshold from database settings
                try:
                    from db.models import Settings as DBSettings
                    with get_session_sync() as session:
                        db_settings = session.get(DBSettings, 1)
                        rate_threshold = db_settings.stuck_high_c if db_settings else settings.smoker_stuck_high_rate_c_per_min
                except Exception as e:
                    logger.error(f"Failed to load alarm threshold from DB: {e}")
                    rate_threshold = settings.smoker_stuck_high_rate_c_per_min
                
                if temp_rate_per_min > rate_threshold:
                    if alert_key not in self.active_alerts:
                        await self._create_alert(
                            alert_key,
                            "stuck_high",
                            "error",
                            f"Stuck high temperature: {temp_c:.1f}°C rising at {temp_rate_per_min:.1f}°C/min (relay off)",
                            {"temp_c": temp_c, "rate": temp_rate_per_min, "relay_state": relay_state}
                        )
                else:
                    await self._clear_alert(alert_key, "Temperature rate returned to normal")
    
    async def _check_sensor_fault_alert(self, status: dict):
        """Check for sensor fault alert."""
        temp_c = status.get("current_temp_c")
        alert_key = "sensor_fault"
        
        if temp_c is None:
            if alert_key not in self.active_alerts:
                await self._create_alert(
                    alert_key,
                    "sensor_fault",
                    "critical",
                    "Temperature sensor fault - no reading available",
                    {"temp_c": temp_c}
                )
        else:
            await self._clear_alert(alert_key, "Sensor reading restored")
    
    async def _check_hardware_fallback_alert(self, status: dict):
        """Check if hardware is using fallback simulation mode."""
        using_fallback = status.get("using_fallback_simulation", False)
        sim_mode = status.get("sim_mode", True)
        alert_key = "hardware_fallback"
        
        # Only alert if NOT in simulation mode but using fallback
        if not sim_mode and using_fallback:
            # Get details about which thermocouples are using fallback
            tc_readings = status.get("thermocouple_readings", {})
            fallback_tcs = []
            
            # Load thermocouple names from database
            try:
                from db.models import Thermocouple
                with get_session_sync() as session:
                    for tc_id, reading in tc_readings.items():
                        if reading.get("mode") == "simulated":
                            tc = session.get(Thermocouple, tc_id)
                            if tc:
                                fallback_tcs.append(f"{tc.name} (pin {tc.cs_pin})")
            except Exception as e:
                logger.error(f"Error loading thermocouple names: {e}")
                fallback_tcs = ["Unknown thermocouples"]
            
            if fallback_tcs and alert_key not in self.active_alerts:
                tc_list = ", ".join(fallback_tcs)
                await self._create_alert(
                    alert_key,
                    "hardware_fallback",
                    "warning",
                    f"Hardware not connected: {tc_list} using simulated data. Check connections!",
                    {
                        "using_fallback": using_fallback,
                        "sim_mode": sim_mode,
                        "fallback_thermocouples": fallback_tcs
                    }
                )
        else:
            await self._clear_alert(alert_key, "All hardware connected properly")
    
    async def _create_alert(self, alert_key: str, alert_type: str, severity: str, message: str, metadata: dict):
        """Create a new alert."""
        # Check debounce
        if alert_key in self.debounce_timers:
            if datetime.utcnow() - self.debounce_timers[alert_key] < self.debounce_duration:
                return  # Still in debounce period
        
        try:
            with get_session_sync() as session:
                alert = Alert(
                    alert_type=alert_type,
                    severity=severity,
                    message=message,
                    active=True,
                    acknowledged=False,
                    meta_data=json.dumps(metadata)
                )
                session.add(alert)
                session.commit()
                session.refresh(alert)  # Ensure we have the ID
                
                alert_id = alert.id
                
                # Store alert ID in active alerts
                self.active_alerts[alert_key] = alert_id
                self.debounce_timers[alert_key] = datetime.utcnow()
                
                # Log event
                event = Event(
                    kind="alert_created",
                    message=f"Alert created: {message}",
                    meta_json=json.dumps({"alert_id": alert_id, "alert_type": alert_type})
                )
                session.add(event)
                session.commit()
                
                logger.warning(f"🚨 Alert created: {message} (ID: {alert_id}, Type: {alert_type}, Severity: {severity})")
                
                # Send webhook if configured (pass ID instead of object)
                logger.info(f"Attempting to send webhook for alert {alert_id}...")
                await self._send_webhook_by_id(alert_id)
                
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
    
    async def _clear_alert(self, alert_key: str, clear_message: str):
        """Clear an active alert."""
        if alert_key not in self.active_alerts:
            return
        
        try:
            alert_id = self.active_alerts[alert_key]
            
            with get_session_sync() as session:
                # Update alert in database
                db_alert = session.get(Alert, alert_id)
                if db_alert:
                    alert_type = db_alert.alert_type
                    db_alert.active = False
                    db_alert.cleared_ts = datetime.utcnow()
                    session.commit()
                    
                    # Log event
                    event = Event(
                        kind="alert_cleared",
                        message=f"Alert cleared: {clear_message}",
                        meta_json=json.dumps({"alert_id": alert_id, "alert_type": alert_type})
                    )
                    session.add(event)
                    session.commit()
                    
                    logger.info(f"Alert cleared: {clear_message}")
                
                # Remove from active alerts
                del self.active_alerts[alert_key]
                if alert_key in self.debounce_timers:
                    del self.debounce_timers[alert_key]
                
        except Exception as e:
            logger.error(f"Failed to clear alert: {e}")
    
    async def acknowledge_alert(self, alert_id: int) -> bool:
        """Acknowledge an alert."""
        try:
            with get_session_sync() as session:
                alert = session.get(Alert, alert_id)
                if alert and alert.active:
                    alert.acknowledged = True
                    session.commit()
                    
                    # Log event
                    event = Event(
                        kind="alert_acknowledged",
                        message=f"Alert acknowledged: {alert.message}",
                        meta_json=json.dumps({"alert_id": alert_id})
                    )
                    session.add(event)
                    session.commit()
                    
                    logger.info(f"Alert {alert_id} acknowledged")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    async def clear_alert(self, alert_id: int) -> bool:
        """Manually clear an alert."""
        try:
            with get_session_sync() as session:
                alert = session.get(Alert, alert_id)
                if alert and alert.active:
                    alert.active = False
                    alert.cleared_ts = datetime.utcnow()
                    session.commit()
                    
                    # Remove from active alerts if present
                    for key, active_alert_id in list(self.active_alerts.items()):
                        if active_alert_id == alert_id:
                            del self.active_alerts[key]
                            break
                    
                    # Log event
                    event = Event(
                        kind="alert_cleared_manual",
                        message=f"Alert manually cleared: {alert.message}",
                        meta_json=json.dumps({"alert_id": alert_id})
                    )
                    session.add(event)
                    session.commit()
                    
                    logger.info(f"Alert {alert_id} manually cleared")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to clear alert {alert_id}: {e}")
            return False
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        try:
            with get_session_sync() as session:
                alerts = session.query(Alert).filter(Alert.active == True).all()
                return alerts
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
    
    async def get_alert_summary(self) -> dict:
        """Get alert summary for WebSocket."""
        active_alerts = await self.get_active_alerts()
        
        summary = {
            "count": len(active_alerts),
            "critical": len([a for a in active_alerts if a.severity == "critical"]),
            "error": len([a for a in active_alerts if a.severity == "error"]),
            "warning": len([a for a in active_alerts if a.severity == "warning"]),
            "info": len([a for a in active_alerts if a.severity == "info"]),
            "unacknowledged": len([a for a in active_alerts if not a.acknowledged])
        }
        
        return summary
    
    async def _send_webhook_by_id(self, alert_id: int):
        """Send webhook notification for alert by ID."""
        # Get webhook URL from database settings (not config file)
        webhook_url = None
        try:
            from db.models import Settings as DBSettings
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                webhook_url = db_settings.webhook_url if db_settings else settings.smoker_webhook_url
        except Exception as e:
            logger.error(f"Failed to load webhook URL from database: {e}")
            webhook_url = settings.smoker_webhook_url
        
        if not webhook_url:
            logger.debug(f"No webhook URL configured, skipping webhook for alert {alert_id}")
            return
        
        # Check rate limiting
        now = datetime.utcnow()
        if (self.last_webhook_time and 
            now - self.last_webhook_time < self.webhook_rate_limit):
            time_remaining = (self.webhook_rate_limit - (now - self.last_webhook_time)).total_seconds()
            logger.warning(f"⏱️ Webhook rate limited for alert {alert_id}. Wait {time_remaining:.0f}s before next webhook.")
            return
        
        logger.info(f"📤 Sending webhook for alert {alert_id} to {webhook_url[:50]}...")
        
        try:
            # Fetch alert from database
            with get_session_sync() as session:
                alert = session.get(Alert, alert_id)
                if not alert:
                    logger.error(f"Alert {alert_id} not found for webhook")
                    return
                
                # Detect Discord webhook and format accordingly
                is_discord = "discord.com/api/webhooks" in webhook_url.lower()
                
                if is_discord:
                    # Discord-specific format with rich embed
                    # Color based on severity
                    color_map = {
                        "critical": 15158332,  # Red
                        "error": 15105570,     # Orange
                        "warning": 16776960,   # Yellow
                        "info": 3447003        # Blue
                    }
                    color = color_map.get(alert.severity, 3447003)
                    
                    # Emoji based on alert type
                    emoji_map = {
                        "high_temp": "🔥",
                        "low_temp": "🧊",
                        "stuck_high": "⚠️",
                        "sensor_fault": "🔌",
                        "hardware_fallback": "🔄"
                    }
                    emoji = emoji_map.get(alert.alert_type, "🚨")
                    
                    payload = {
                        "username": "PiTmaster Alert",
                        "embeds": [{
                            "title": f"{emoji} {alert.alert_type.replace('_', ' ').title()}",
                            "description": alert.message,
                            "color": color,
                            "fields": [
                                {
                                    "name": "Severity",
                                    "value": alert.severity.upper(),
                                    "inline": True
                                },
                                {
                                    "name": "Alert ID",
                                    "value": str(alert.id),
                                    "inline": True
                                }
                            ],
                            "timestamp": alert.ts.isoformat(),
                            "footer": {
                                "text": "PiTmaster Smoker Controller"
                            }
                        }]
                    }
                    
                    # Add metadata fields if present
                    if alert.meta_data:
                        try:
                            metadata = json.loads(alert.meta_data)
                            if "temp_c" in metadata:
                                temp_f = (metadata["temp_c"] * 9/5) + 32
                                payload["embeds"][0]["fields"].append({
                                    "name": "Temperature",
                                    "value": f"{temp_f:.1f}°F ({metadata['temp_c']:.1f}°C)",
                                    "inline": True
                                })
                            if "threshold" in metadata:
                                thresh_f = (metadata["threshold"] * 9/5) + 32
                                payload["embeds"][0]["fields"].append({
                                    "name": "Threshold",
                                    "value": f"{thresh_f:.1f}°F ({metadata['threshold']:.1f}°C)",
                                    "inline": True
                                })
                        except:
                            pass
                else:
                    # Generic format for other webhooks
                    payload = {
                        "alert_id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "timestamp": alert.ts.isoformat(),
                        "metadata": json.loads(alert.meta_data) if alert.meta_data else {}
                    }
            
            response = await self.webhook_client.post(
                webhook_url,
                json=payload
            )
            response.raise_for_status()
            
            self.last_webhook_time = now
            logger.info(f"✅ Webhook sent successfully for alert {alert_id} to {webhook_url[:50]}... (Discord: {is_discord}, Status: {response.status_code})")
            
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.webhook_client.aclose()

