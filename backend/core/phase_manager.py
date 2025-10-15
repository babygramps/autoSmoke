"""Phase state machine management for cooking sessions."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from collections import deque

from db.models import Smoke, SmokePhase, ThermocoupleReading, Reading
from db.session import get_session_sync
from sqlmodel import select

logger = logging.getLogger(__name__)


class PhaseManager:
    """Manages cooking phase state machine and transitions."""
    
    def __init__(self):
        # Track temperature stability per smoke session
        self._stability_history: Dict[int, deque] = {}  # smoke_id -> deque of (timestamp, temp_f)
        self._stability_window_seconds = 60  # Track last 60 seconds for stability checks
        
        # Track meat temperature history for stall detection
        self._meat_temp_history: Dict[int, deque] = {}  # smoke_id -> deque of (timestamp, meat_temp_f)
        self._stall_detection_window_minutes = 45
        
    def get_current_phase(self, smoke_id: int) -> Optional[SmokePhase]:
        """Get the current active phase for a smoke session."""
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke or not smoke.current_phase_id:
                    return None
                
                phase = session.get(SmokePhase, smoke.current_phase_id)
                return phase
        except Exception as e:
            logger.error(f"Failed to get current phase for smoke {smoke_id}: {e}")
            return None
    
    def get_next_phase(self, smoke_id: int) -> Optional[SmokePhase]:
        """Get the next phase in sequence."""
        try:
            with get_session_sync() as session:
                current_phase = self.get_current_phase(smoke_id)
                if not current_phase:
                    return None
                
                # Find next phase by phase_order
                statement = (
                    select(SmokePhase)
                    .where(SmokePhase.smoke_id == smoke_id)
                    .where(SmokePhase.phase_order == current_phase.phase_order + 1)
                )
                next_phase = session.exec(statement).first()
                return next_phase
        except Exception as e:
            logger.error(f"Failed to get next phase for smoke {smoke_id}: {e}")
            return None
    
    def check_phase_conditions(
        self, 
        smoke_id: int, 
        current_temp_f: float,
        meat_temp_f: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if current phase completion conditions are met.
        
        Returns:
            (conditions_met, reason) - reason explains which condition was met
        """
        try:
            current_phase = self.get_current_phase(smoke_id)
            if not current_phase:
                return (False, None)
            
            conditions = json.loads(current_phase.completion_conditions)
            now = datetime.utcnow()
            phase_duration_minutes = (now - current_phase.started_at).total_seconds() / 60
            
            # Check max duration (always a valid exit condition)
            if "max_duration_min" in conditions:
                if phase_duration_minutes >= conditions["max_duration_min"]:
                    logger.info(f"Phase {current_phase.phase_name} max duration reached: {phase_duration_minutes:.1f} min")
                    return (True, f"Maximum duration of {conditions['max_duration_min']} minutes reached")
            
            # Check temperature stability
            if "stability_range_f" in conditions and "stability_duration_min" in conditions:
                stability_met = self._check_temperature_stability(
                    smoke_id,
                    current_temp_f,
                    current_phase.target_temp_f,
                    conditions["stability_range_f"],
                    conditions["stability_duration_min"]
                )
                if stability_met:
                    logger.info(f"Phase {current_phase.phase_name} temperature stability achieved")
                    return (True, f"Temperature stable at {current_phase.target_temp_f:.0f}°F ±{conditions['stability_range_f']:.0f}°F for {conditions['stability_duration_min']} minutes")
            
            # Check meat temperature threshold (if meat probe is configured)
            if "meat_temp_threshold_f" in conditions and meat_temp_f is not None:
                if meat_temp_f >= conditions["meat_temp_threshold_f"]:
                    logger.info(f"Phase {current_phase.phase_name} meat temp threshold reached: {meat_temp_f:.1f}°F")
                    return (True, f"Meat temperature reached {meat_temp_f:.1f}°F")
            
            # Conditions not yet met
            return (False, None)
            
        except Exception as e:
            logger.error(f"Failed to check phase conditions for smoke {smoke_id}: {e}")
            return (False, None)
    
    def _check_temperature_stability(
        self,
        smoke_id: int,
        current_temp_f: float,
        target_temp_f: float,
        range_f: float,
        duration_minutes: int
    ) -> bool:
        """Check if temperature has been stable within range for required duration."""
        try:
            # Initialize history for this smoke if needed
            if smoke_id not in self._stability_history:
                self._stability_history[smoke_id] = deque(maxlen=100)
            
            history = self._stability_history[smoke_id]
            now = datetime.utcnow()
            
            # Add current reading
            history.append((now, current_temp_f))
            
            # Remove old readings outside the window
            cutoff_time = now - timedelta(minutes=duration_minutes)
            while history and history[0][0] < cutoff_time:
                history.popleft()
            
            # Check if we have enough history
            if not history:
                return False
            
            # Check if oldest reading is old enough
            oldest_time = history[0][0]
            if (now - oldest_time).total_seconds() < (duration_minutes * 60):
                return False
            
            # Check if all readings in the window are within range
            min_temp = target_temp_f - range_f
            max_temp = target_temp_f + range_f
            
            for timestamp, temp in history:
                if temp < min_temp or temp > max_temp:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check temperature stability: {e}")
            return False
    
    def detect_stall(
        self,
        smoke_id: int,
        meat_temp_f: Optional[float]
    ) -> bool:
        """
        Detect meat temperature stall.
        
        Stall is detected when meat temp rises <1-2°F over 30-45 min around 150-170°F.
        """
        if meat_temp_f is None:
            return False
        
        try:
            # Only check for stall in the typical range
            if meat_temp_f < 140 or meat_temp_f > 180:
                return False
            
            # Initialize history for this smoke if needed
            if smoke_id not in self._meat_temp_history:
                self._meat_temp_history[smoke_id] = deque(maxlen=100)
            
            history = self._meat_temp_history[smoke_id]
            now = datetime.utcnow()
            
            # Add current reading
            history.append((now, meat_temp_f))
            
            # Remove old readings
            cutoff_time = now - timedelta(minutes=self._stall_detection_window_minutes)
            while history and history[0][0] < cutoff_time:
                history.popleft()
            
            # Need at least 30 minutes of history
            if not history or (now - history[0][0]).total_seconds() < (30 * 60):
                return False
            
            # Check temperature rise over the window
            oldest_temp = history[0][1]
            temp_rise = meat_temp_f - oldest_temp
            
            # Stall detected if temp rose less than 2°F in the window
            if temp_rise < 2.0:
                logger.info(f"Stall detected: meat temp only rose {temp_rise:.1f}°F in last {self._stall_detection_window_minutes} minutes")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to detect stall: {e}")
            return False
    
    def request_phase_transition(self, smoke_id: int, reason: str) -> bool:
        """
        Set pending_phase_transition flag and prepare for user approval.
        
        Returns True if transition was requested, False if already pending or error.
        """
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke:
                    logger.error(f"Smoke {smoke_id} not found")
                    return False
                
                if smoke.pending_phase_transition:
                    # Already pending
                    return False
                
                smoke.pending_phase_transition = True
                session.commit()
                
                logger.info(f"Phase transition requested for smoke {smoke_id}: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to request phase transition for smoke {smoke_id}: {e}")
            return False
    
    def approve_phase_transition(self, smoke_id: int) -> Tuple[bool, Optional[str]]:
        """
        Approve and execute phase transition.
        
        Returns:
            (success, error_message)
        """
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke:
                    return (False, "Smoke session not found")
                
                if not smoke.pending_phase_transition:
                    return (False, "No pending phase transition")
                
                # Get current and next phases
                current_phase = None
                if smoke.current_phase_id:
                    current_phase = session.get(SmokePhase, smoke.current_phase_id)
                
                if current_phase:
                    # End current phase
                    current_phase.is_active = False
                    current_phase.ended_at = datetime.utcnow()
                    duration = (current_phase.ended_at - current_phase.started_at).total_seconds() / 60
                    current_phase.actual_duration_minutes = int(duration)
                    
                    # Find next phase
                    statement = (
                        select(SmokePhase)
                        .where(SmokePhase.smoke_id == smoke_id)
                        .where(SmokePhase.phase_order == current_phase.phase_order + 1)
                    )
                    next_phase = session.exec(statement).first()
                else:
                    # No current phase, get first phase
                    statement = (
                        select(SmokePhase)
                        .where(SmokePhase.smoke_id == smoke_id)
                        .where(SmokePhase.phase_order == 0)
                    )
                    next_phase = session.exec(statement).first()
                
                if not next_phase:
                    # No more phases - session complete
                    smoke.pending_phase_transition = False
                    smoke.current_phase_id = None
                    session.commit()
                    logger.info(f"All phases complete for smoke {smoke_id}")
                    return (True, None)
                
                # Start next phase
                next_phase.is_active = True
                next_phase.started_at = datetime.utcnow()
                smoke.current_phase_id = next_phase.id
                smoke.pending_phase_transition = False
                
                # Clear stability history for new phase
                if smoke_id in self._stability_history:
                    self._stability_history[smoke_id].clear()
                
                session.commit()
                
                logger.info(f"Phase transition approved for smoke {smoke_id}: {current_phase.phase_name if current_phase else 'None'} -> {next_phase.phase_name}")
                
                return (True, None)
                
        except Exception as e:
            error_msg = f"Failed to approve phase transition: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    def update_phase(
        self,
        phase_id: int,
        target_temp_f: Optional[float] = None,
        completion_conditions: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Update phase parameters.
        
        Returns:
            (success, error_message)
        """
        try:
            with get_session_sync() as session:
                phase = session.get(SmokePhase, phase_id)
                if not phase:
                    return (False, "Phase not found")
                
                if target_temp_f is not None:
                    phase.target_temp_f = target_temp_f
                
                if completion_conditions is not None:
                    phase.completion_conditions = json.dumps(completion_conditions)
                
                session.commit()
                
                logger.info(f"Updated phase {phase_id}: {phase.phase_name}")
                return (True, None)
                
        except Exception as e:
            error_msg = f"Failed to update phase: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    def skip_phase(self, smoke_id: int) -> Tuple[bool, Optional[str]]:
        """
        Skip current phase and move to next.
        
        Returns:
            (success, error_message)
        """
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke:
                    return (False, "Smoke session not found")
                
                # Set pending transition (will be auto-approved immediately)
                smoke.pending_phase_transition = True
                session.commit()
            
            # Approve the transition
            return self.approve_phase_transition(smoke_id)
            
        except Exception as e:
            error_msg = f"Failed to skip phase: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    def pause_phase(self, smoke_id: int) -> Tuple[bool, Optional[str]]:
        """
        Pause the current phase.
        
        When paused, phase condition checking is disabled but temperature control continues.
        
        Returns:
            (success, error_message)
        """
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke or not smoke.current_phase_id:
                    return (False, "No active phase to pause")
                
                current_phase = session.get(SmokePhase, smoke.current_phase_id)
                if not current_phase:
                    return (False, "Current phase not found")
                
                if current_phase.is_paused:
                    return (False, "Phase is already paused")
                
                current_phase.is_paused = True
                session.commit()
                
                logger.info(f"Paused phase {current_phase.phase_name} for smoke {smoke_id}")
                return (True, None)
                
        except Exception as e:
            error_msg = f"Failed to pause phase: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    def resume_phase(self, smoke_id: int) -> Tuple[bool, Optional[str]]:
        """
        Resume the current paused phase.
        
        Returns:
            (success, error_message)
        """
        try:
            with get_session_sync() as session:
                smoke = session.get(Smoke, smoke_id)
                if not smoke or not smoke.current_phase_id:
                    return (False, "No active phase to resume")
                
                current_phase = session.get(SmokePhase, smoke.current_phase_id)
                if not current_phase:
                    return (False, "Current phase not found")
                
                if not current_phase.is_paused:
                    return (False, "Phase is not paused")
                
                current_phase.is_paused = False
                
                # Clear stability history when resuming to avoid false completions
                if smoke_id in self._stability_history:
                    self._stability_history[smoke_id].clear()
                
                session.commit()
                
                logger.info(f"Resumed phase {current_phase.phase_name} for smoke {smoke_id}")
                return (True, None)
                
        except Exception as e:
            error_msg = f"Failed to resume phase: {str(e)}"
            logger.error(error_msg)
            return (False, error_msg)
    
    def get_phase_progress(self, smoke_id: int, current_temp_f: float, meat_temp_f: Optional[float] = None) -> Dict[str, Any]:
        """
        Get progress information for current phase.
        
        Returns dict with progress percentage, conditions status, etc.
        """
        try:
            current_phase = self.get_current_phase(smoke_id)
            if not current_phase:
                return {"has_phase": False}
            
            conditions = json.loads(current_phase.completion_conditions)
            now = datetime.utcnow()
            phase_duration_minutes = (now - current_phase.started_at).total_seconds() / 60
            
            progress_factors = []
            
            # Check each condition and calculate progress
            if "max_duration_min" in conditions:
                duration_progress = min(100, (phase_duration_minutes / conditions["max_duration_min"]) * 100)
                progress_factors.append({
                    "type": "duration",
                    "progress": duration_progress,
                    "current": phase_duration_minutes,
                    "target": conditions["max_duration_min"],
                    "met": phase_duration_minutes >= conditions["max_duration_min"]
                })
            
            if "stability_range_f" in conditions and "stability_duration_min" in conditions:
                # Check how long we've been stable
                in_range = abs(current_temp_f - current_phase.target_temp_f) <= conditions["stability_range_f"]
                
                # Estimate stability duration (simplified)
                stability_duration = 0
                if smoke_id in self._stability_history:
                    history = self._stability_history[smoke_id]
                    if history:
                        stability_duration = (now - history[0][0]).total_seconds() / 60
                
                stability_progress = min(100, (stability_duration / conditions["stability_duration_min"]) * 100)
                progress_factors.append({
                    "type": "stability",
                    "progress": stability_progress,
                    "current": stability_duration,
                    "target": conditions["stability_duration_min"],
                    "in_range": in_range,
                    "met": stability_progress >= 100
                })
            
            if "meat_temp_threshold_f" in conditions and meat_temp_f is not None:
                meat_progress = min(100, (meat_temp_f / conditions["meat_temp_threshold_f"]) * 100)
                progress_factors.append({
                    "type": "meat_temp",
                    "progress": meat_progress,
                    "current": meat_temp_f,
                    "target": conditions["meat_temp_threshold_f"],
                    "met": meat_temp_f >= conditions["meat_temp_threshold_f"]
                })
            
            # Overall progress is the minimum of all factors (all must be met)
            overall_progress = min([f["progress"] for f in progress_factors]) if progress_factors else 0
            
            return {
                "has_phase": True,
                "phase_name": current_phase.phase_name,
                "phase_order": current_phase.phase_order,
                "target_temp_f": current_phase.target_temp_f,
                "duration_minutes": phase_duration_minutes,
                "overall_progress": overall_progress,
                "progress_factors": progress_factors,
                "conditions_met": any(f.get("met", False) for f in progress_factors)
            }
            
        except Exception as e:
            logger.error(f"Failed to get phase progress: {e}")
            return {"has_phase": False, "error": str(e)}


# Global phase manager instance
phase_manager = PhaseManager()

