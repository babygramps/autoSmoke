"""Adaptive PID controller with continuous self-tuning.

This module implements a self-tuning PID controller that continuously monitors
performance and makes gradual adjustments to optimize control without disruption.
"""

import logging
import time
from typing import Optional, Tuple, List
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """PID performance metrics for a time window."""
    avg_error: float
    avg_abs_error: float
    oscillation_score: float  # 0-1, higher = more oscillation
    overshoot_detected: bool
    settling_time: float  # Time to reach steady state


class AdaptivePIDController:
    """
    Self-tuning PID controller that continuously optimizes gains.
    
    This controller monitors performance and makes small, gradual adjustments
    to PID gains to optimize control without disrupting operation.
    """
    
    def __init__(
        self,
        min_kp: float = 1.0,
        max_kp: float = 15.0,
        min_ki: float = 0.01,
        max_ki: float = 1.0,
        min_kd: float = 5.0,
        max_kd: float = 50.0,
        adjustment_rate: float = 0.05,  # Max 5% change per adjustment
        evaluation_window: int = 300,  # 5 minutes of data
        adjustment_cooldown: int = 600,  # 10 minutes between adjustments
    ):
        """
        Initialize adaptive PID controller.
        
        Args:
            min_kp, max_kp: Bounds for proportional gain
            min_ki, max_ki: Bounds for integral gain
            min_kd, max_kd: Bounds for derivative gain
            adjustment_rate: Maximum fractional change per adjustment (0.05 = 5%)
            evaluation_window: Seconds of data to evaluate (300 = 5 min)
            adjustment_cooldown: Seconds to wait between adjustments (600 = 10 min)
        """
        self.min_kp = min_kp
        self.max_kp = max_kp
        self.min_ki = min_ki
        self.max_ki = max_ki
        self.min_kd = min_kd
        self.max_kd = max_kd
        self.adjustment_rate = adjustment_rate
        self.evaluation_window = evaluation_window
        self.adjustment_cooldown = adjustment_cooldown
        
        # Performance data buffers
        self.errors = deque(maxlen=evaluation_window)  # Circular buffer
        self.timestamps = deque(maxlen=evaluation_window)
        self.temps = deque(maxlen=evaluation_window)
        self.setpoints = deque(maxlen=evaluation_window)
        
        # State tracking
        self.last_adjustment_time: Optional[float] = None
        self.adjustment_count = 0
        self.enabled = False
        
        # Recent adjustments log (for UI display)
        self.adjustment_history: List[dict] = []
        self.max_history = 20
        
    def enable(self):
        """Enable adaptive tuning."""
        if not self.enabled:
            self.enabled = True
            logger.info("Adaptive PID tuning enabled")
    
    def disable(self):
        """Disable adaptive tuning."""
        if self.enabled:
            self.enabled = False
            logger.info("Adaptive PID tuning disabled")
    
    def record_sample(self, temp: float, setpoint: float, error: float):
        """
        Record a sample for performance evaluation.
        
        Args:
            temp: Current temperature
            setpoint: Target temperature
            error: Control error (setpoint - temp)
        """
        if not self.enabled:
            return
        
        current_time = time.time()
        self.errors.append(error)
        self.timestamps.append(current_time)
        self.temps.append(temp)
        self.setpoints.append(setpoint)
    
    def should_adjust(self) -> bool:
        """
        Check if it's time to evaluate and potentially adjust gains.
        
        Returns:
            True if adjustment should be considered
        """
        if not self.enabled:
            return False
        
        # Need enough data
        if len(self.errors) < self.evaluation_window * 0.8:  # At least 80% full
            return False
        
        # Check cooldown
        if self.last_adjustment_time is not None:
            time_since_last = time.time() - self.last_adjustment_time
            if time_since_last < self.adjustment_cooldown:
                return False
        
        return True
    
    def evaluate_and_adjust(
        self,
        current_kp: float,
        current_ki: float,
        current_kd: float
    ) -> Optional[Tuple[float, float, float, str]]:
        """
        Evaluate performance and suggest gain adjustments.
        
        Args:
            current_kp: Current proportional gain
            current_ki: Current integral gain
            current_kd: Current derivative gain
            
        Returns:
            Tuple of (new_kp, new_ki, new_kd, reason) if adjustment recommended,
            None if no adjustment needed
        """
        if not self.should_adjust():
            return None
        
        # Calculate performance metrics
        metrics = self._calculate_metrics()
        
        # Decide on adjustments based on performance
        adjustment = self._decide_adjustment(metrics, current_kp, current_ki, current_kd)
        
        if adjustment:
            new_kp, new_ki, new_kd, reason = adjustment
            
            # Apply bounds
            new_kp = max(self.min_kp, min(self.max_kp, new_kp))
            new_ki = max(self.min_ki, min(self.max_ki, new_ki))
            new_kd = max(self.min_kd, min(self.max_kd, new_kd))
            
            # Record adjustment
            self.last_adjustment_time = time.time()
            self.adjustment_count += 1
            
            # Log to history
            self.adjustment_history.append({
                "timestamp": self.last_adjustment_time,
                "old_kp": current_kp,
                "old_ki": current_ki,
                "old_kd": current_kd,
                "new_kp": new_kp,
                "new_ki": new_ki,
                "new_kd": new_kd,
                "reason": reason,
                "metrics": {
                    "avg_error": metrics.avg_error,
                    "oscillation": metrics.oscillation_score,
                    "overshoot": metrics.overshoot_detected
                }
            })
            
            # Keep history bounded
            if len(self.adjustment_history) > self.max_history:
                self.adjustment_history.pop(0)
            
            logger.info(f"🎯 Adaptive PID adjustment #{self.adjustment_count}")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   Kp: {current_kp:.4f} → {new_kp:.4f} ({((new_kp/current_kp - 1) * 100):.1f}%)")
            logger.info(f"   Ki: {current_ki:.4f} → {new_ki:.4f} ({((new_ki/current_ki - 1) * 100):.1f}%)")
            logger.info(f"   Kd: {current_kd:.4f} → {new_kd:.4f} ({((new_kd/current_kd - 1) * 100):.1f}%)")
            
            return (new_kp, new_ki, new_kd, reason)
        
        return None
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics from buffered data."""
        errors_list = list(self.errors)
        temps_list = list(self.temps)
        setpoints_list = list(self.setpoints)
        
        # Average error (bias)
        avg_error = sum(errors_list) / len(errors_list)
        
        # Average absolute error
        avg_abs_error = sum(abs(e) for e in errors_list) / len(errors_list)
        
        # Oscillation detection: count zero crossings and measure variation
        zero_crossings = 0
        for i in range(1, len(errors_list)):
            if (errors_list[i] > 0) != (errors_list[i-1] > 0):
                zero_crossings += 1
        
        # Normalize oscillation score (more crossings = more oscillation)
        oscillation_score = min(1.0, zero_crossings / (len(errors_list) * 0.1))
        
        # Overshoot detection: did we cross setpoint significantly?
        overshoot_detected = False
        for i in range(len(temps_list)):
            if abs(temps_list[i] - setpoints_list[i]) > 2.0:  # >2°C overshoot
                overshoot_detected = True
                break
        
        # Settling time: how long to get within acceptable range?
        settling_time = 0.0
        target_error = 0.5  # Within 0.5°C is "settled"
        for i, error in enumerate(errors_list):
            if abs(error) > target_error:
                settling_time = i  # Still settling
        
        return PerformanceMetrics(
            avg_error=avg_error,
            avg_abs_error=avg_abs_error,
            oscillation_score=oscillation_score,
            overshoot_detected=overshoot_detected,
            settling_time=settling_time
        )
    
    def _decide_adjustment(
        self,
        metrics: PerformanceMetrics,
        kp: float,
        ki: float,
        kd: float
    ) -> Optional[Tuple[float, float, float, str]]:
        """
        Decide what adjustment to make based on metrics.
        
        Returns:
            Tuple of (new_kp, new_ki, new_kd, reason) or None
        """
        # Priority order: oscillation > overshoot > steady-state error > sluggish
        
        # 1. Too much oscillation - reduce aggressiveness
        if metrics.oscillation_score > 0.6:
            new_kp = kp * (1 - self.adjustment_rate)  # Reduce Kp
            new_kd = kd * (1 - self.adjustment_rate * 0.5)  # Slightly reduce Kd
            return (new_kp, ki, new_kd, f"Reducing oscillation (score={metrics.oscillation_score:.2f})")
        
        # 2. Overshoot - increase damping
        if metrics.overshoot_detected and kd < self.max_kd * 0.9:
            new_kd = kd * (1 + self.adjustment_rate)  # Increase Kd for damping
            new_kp = kp * (1 - self.adjustment_rate * 0.3)  # Slightly reduce Kp
            return (new_kp, ki, new_kd, "Increasing damping to reduce overshoot")
        
        # 3. Persistent steady-state error - increase integral action
        if abs(metrics.avg_error) > 1.0 and ki < self.max_ki * 0.9:
            # Only increase Ki if error is consistent (not oscillating)
            if metrics.oscillation_score < 0.3:
                new_ki = ki * (1 + self.adjustment_rate * 0.5)  # Small Ki increase
                return (kp, new_ki, kd, f"Correcting steady-state error ({metrics.avg_error:.2f}°C)")
        
        # 4. Sluggish response - increase responsiveness
        if metrics.settling_time > 200 and metrics.avg_abs_error > 1.5:  # Taking >3min to settle
            if metrics.oscillation_score < 0.3:  # Only if not oscillating
                new_kp = kp * (1 + self.adjustment_rate)  # Increase Kp
                return (new_kp, ki, kd, f"Increasing responsiveness (settling time={metrics.settling_time:.0f}s)")
        
        # 5. System is performing well - no adjustment needed
        if metrics.avg_abs_error < 0.5 and metrics.oscillation_score < 0.2:
            logger.debug(f"✓ PID performing well (error={metrics.avg_abs_error:.2f}°C, oscillation={metrics.oscillation_score:.2f})")
        
        return None
    
    def get_status(self) -> dict:
        """Get adaptive tuning status for display."""
        return {
            "enabled": self.enabled,
            "adjustment_count": self.adjustment_count,
            "last_adjustment": self.last_adjustment_time,
            "cooldown_remaining": max(0, self.adjustment_cooldown - (time.time() - self.last_adjustment_time)) if self.last_adjustment_time else 0,
            "data_points": len(self.errors),
            "recent_adjustments": self.adjustment_history[-5:] if self.adjustment_history else []
        }
    
    def reset(self):
        """Reset all buffers and state."""
        self.errors.clear()
        self.timestamps.clear()
        self.temps.clear()
        self.setpoints.clear()
        self.last_adjustment_time = None
        logger.info("Adaptive PID state reset")

