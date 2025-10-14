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
                
                logger.warning(f"Alert created: {message}")
                
                # Send webhook if configured (pass ID instead of object)
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
        if not settings.smoker_webhook_url:
            return
        
        # Check rate limiting
        now = datetime.utcnow()
        if (self.last_webhook_time and 
            now - self.last_webhook_time < self.webhook_rate_limit):
            logger.debug("Webhook rate limited")
            return
        
        try:
            # Fetch alert from database
            with get_session_sync() as session:
                alert = session.get(Alert, alert_id)
                if not alert:
                    logger.error(f"Alert {alert_id} not found for webhook")
                    return
                
                payload = {
                    "alert_id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.ts.isoformat(),
                    "metadata": json.loads(alert.meta_data) if alert.meta_data else {}
                }
            
            response = await self.webhook_client.post(
                settings.smoker_webhook_url,
                json=payload
            )
            response.raise_for_status()
            
            self.last_webhook_time = now
            logger.info(f"Webhook sent for alert {alert_id}")
            
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
    
    async def cleanup(self):
        """Cleanup resources."""
        await self.webhook_client.aclose()


# Global alert manager instance
alert_manager = AlertManager()
