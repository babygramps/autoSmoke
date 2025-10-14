"""WebSocket manager for real-time telemetry."""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from core.controller import controller
from core.alerts import alert_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and broadcasting."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.broadcast_task = None
        self.running = False
    
    async def start_broadcasting(self):
        """Start the broadcast task."""
        if not self.running:
            self.running = True
            self.broadcast_task = asyncio.create_task(self._broadcast_loop())
            logger.info("WebSocket broadcasting started")
    
    async def stop_broadcasting(self):
        """Stop the broadcast task."""
        if self.running:
            self.running = False
            if self.broadcast_task:
                self.broadcast_task.cancel()
                try:
                    await self.broadcast_task
                except asyncio.CancelledError:
                    pass
            logger.info("WebSocket broadcasting stopped")
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return
        
        # Create a copy of the list to avoid modification during iteration
        connections_to_remove = []
        
        for connection in self.active_connections:
            try:
                if connection.client_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
                else:
                    connections_to_remove.append(connection)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                connections_to_remove.append(connection)
        
        # Remove dead connections
        for connection in connections_to_remove:
            self.disconnect(connection)
    
    async def _broadcast_loop(self):
        """Main broadcast loop running at 1 Hz."""
        while self.running:
            try:
                # Get current controller status
                status = controller.get_status()
                
                # Get alert summary and alerts
                alert_summary = await alert_manager.get_alert_summary()
                alerts = await alert_manager.get_active_alerts()
                
                # Create telemetry message
                telemetry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "type": "telemetry",
                    "data": {
                        "running": status["running"],
                        "boost_active": status["boost_active"],
                        "boost_until": status["boost_until"],
                        "control_mode": status["control_mode"],
                        "active_smoke_id": status["active_smoke_id"],
                        "current_temp_c": status["current_temp_c"],
                        "current_temp_f": status["current_temp_f"],
                        "setpoint_c": status["setpoint_c"],
                        "setpoint_f": status["setpoint_f"],
                        "pid_output": status["pid_output"],
                        "output_bool": status["output_bool"],
                        "relay_state": status["relay_state"],
                        "loop_count": status["loop_count"],
                        "last_loop_time": status["last_loop_time"],
                        "thermocouple_readings": status["thermocouple_readings"],
                        "alert_summary": alert_summary,
                        "alerts": [
                            {
                                "id": alert.id,
                                "ts": alert.ts.isoformat() + 'Z' if not alert.ts.isoformat().endswith('Z') else alert.ts.isoformat(),
                                "alert_type": alert.alert_type,
                                "severity": alert.severity,
                                "message": alert.message,
                                "active": alert.active,
                                "acknowledged": alert.acknowledged,
                                "cleared_ts": (alert.cleared_ts.isoformat() + 'Z' if not alert.cleared_ts.isoformat().endswith('Z') else alert.cleared_ts.isoformat()) if alert.cleared_ts else None,
                                "metadata": alert.meta_data
                            }
                            for alert in alerts
                        ]
                    }
                }
                
                # Broadcast to all connected clients
                await self.broadcast(json.dumps(telemetry))
                
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
            
            # Wait for next broadcast (1 Hz)
            await asyncio.sleep(1.0)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time telemetry."""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive by waiting for client messages
            # (or ping/pong if needed)
            data = await websocket.receive_text()
            
            # Handle client messages if needed
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}),
                        websocket
                    )
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON from client: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def start_websocket_broadcasting():
    """Start WebSocket broadcasting (called on app startup)."""
    await manager.start_broadcasting()


async def stop_websocket_broadcasting():
    """Stop WebSocket broadcasting (called on app shutdown)."""
    await manager.stop_broadcasting()
