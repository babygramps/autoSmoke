"""Service responsible for smoke session coordination."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional, Tuple

from core.config import settings
from core.phase_manager import phase_manager
from db.models import Smoke, SmokePhase
from db.session import get_session_sync

logger = logging.getLogger(__name__)


@dataclass
class SessionLoadResult:
    smoke_id: Optional[int]
    phase_setpoint_f: Optional[float] = None


class SessionService:
    """Handle smoke session and phase coordination."""

    def __init__(self) -> None:
        self.active_smoke_id: Optional[int] = None

    def load_active_smoke(self) -> SessionLoadResult:
        try:
            with get_session_sync() as session:
                from sqlmodel import select

                statement = select(Smoke).where(Smoke.is_active == True)
                active_smoke = session.exec(statement).first()

                if not active_smoke:
                    logger.info("No active smoke session found")
                    self.active_smoke_id = None
                    return SessionLoadResult(smoke_id=None)

                self.active_smoke_id = active_smoke.id
                logger.info("Loaded active smoke session: %s (ID: %s)", active_smoke.name, active_smoke.id)

                current_phase = phase_manager.get_current_phase(active_smoke.id)
                if current_phase:
                    logger.info(
                        "Applied phase setpoint from loaded session: %s @ %s°F",
                        current_phase.phase_name,
                        current_phase.target_temp_f,
                    )
                    return SessionLoadResult(active_smoke.id, current_phase.target_temp_f)

                return SessionLoadResult(active_smoke.id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load active smoke: %s", exc)
            self.active_smoke_id = None
            return SessionLoadResult(smoke_id=None)

    def set_active_smoke(self, smoke_id: int) -> SessionLoadResult:
        self.active_smoke_id = smoke_id
        logger.info("Active smoke session set to ID: %s", smoke_id)

        try:
            current_phase = phase_manager.get_current_phase(smoke_id)
            if current_phase:
                logger.info(
                    "Applied phase setpoint: %s @ %s°F",
                    current_phase.phase_name,
                    current_phase.target_temp_f,
                )
                return SessionLoadResult(smoke_id, current_phase.target_temp_f)
            logger.warning("No active phase found for smoke %s, setpoint not changed", smoke_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to load phase settings for smoke %s: %s", smoke_id, exc)

        return SessionLoadResult(smoke_id)

    async def check_phase_conditions(
        self,
        temp_c: float,
        tc_readings: Dict[int, Tuple[Optional[float], bool]],
        log_event: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        if not self.active_smoke_id:
            return

        try:
            from ws.manager import manager as ws_manager

            with get_session_sync() as session:
                smoke = session.get(Smoke, self.active_smoke_id)
                if not smoke or not smoke.current_phase_id or smoke.pending_phase_transition:
                    return

                current_phase = session.get(SmokePhase, smoke.current_phase_id)
                if not current_phase or current_phase.is_paused:
                    return

                meat_probe_tc_id = smoke.meat_probe_tc_id

            meat_temp_f = None
            if meat_probe_tc_id and meat_probe_tc_id in tc_readings:
                meat_temp_c, fault = tc_readings[meat_probe_tc_id]
                if not fault and meat_temp_c is not None:
                    meat_temp_f = settings.celsius_to_fahrenheit(meat_temp_c)

            current_temp_f = settings.celsius_to_fahrenheit(temp_c)
            conditions_met, reason = phase_manager.check_phase_conditions(
                self.active_smoke_id,
                current_temp_f,
                meat_temp_f,
            )

            if not conditions_met:
                return

            success = phase_manager.request_phase_transition(self.active_smoke_id, reason)
            if not success:
                return

            logger.info("Phase transition requested for smoke %s: %s", self.active_smoke_id, reason)

            current_phase = phase_manager.get_current_phase(self.active_smoke_id)
            next_phase = phase_manager.get_next_phase(self.active_smoke_id)

            await ws_manager.broadcast_phase_event(
                "phase_transition_ready",
                {
                    "smoke_id": self.active_smoke_id,
                    "reason": reason,
                    "current_phase": {
                        "id": current_phase.id,
                        "phase_name": current_phase.phase_name,
                        "target_temp_f": current_phase.target_temp_f,
                    }
                    if current_phase
                    else None,
                    "next_phase": {
                        "id": next_phase.id,
                        "phase_name": next_phase.phase_name,
                        "target_temp_f": next_phase.target_temp_f,
                    }
                    if next_phase
                    else None,
                },
            )

            if log_event:
                await log_event(
                    "phase_transition_ready",
                    f"Phase transition ready: {reason}",
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to check phase conditions: %s", exc)

    def get_current_phase_info(self) -> Optional[dict]:
        if not self.active_smoke_id:
            return None

        try:
            current_phase = phase_manager.get_current_phase(self.active_smoke_id)
            if not current_phase:
                return None

            return {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "phase_order": current_phase.phase_order,
                "target_temp_f": current_phase.target_temp_f,
                "started_at": current_phase.started_at.isoformat() if current_phase.started_at else None,
                "is_active": current_phase.is_active,
                "completion_conditions": json.loads(current_phase.completion_conditions),
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to get current phase info: %s", exc)
            return None
