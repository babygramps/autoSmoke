"""PID Auto-Tuner using Relay Oscillation Method.

This implementation uses the relay feedback method (Åström-Hägglund method) to
automatically determine optimal PID parameters. The method works by:

1. Applying a relay (on/off) control to induce oscillations in the system
2. Measuring the oscillation characteristics (amplitude and period)
3. Computing PID gains using various tuning rules (Ziegler-Nichols, Tyreus-Luyben, etc.)

This is particularly well-suited for temperature control systems like smokers.
"""

import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Tuple, List
import math

logger = logging.getLogger(__name__)


class TuningRule(str, Enum):
    """Available PID tuning rules."""
    ZIEGLER_NICHOLS_PID = "ziegler_nichols_pid"
    ZIEGLER_NICHOLS_PI = "ziegler_nichols_pi"
    ZIEGLER_NICHOLS_P = "ziegler_nichols_p"
    TYREUS_LUYBEN = "tyreus_luyben"
    CIANCONE_MARLIN = "ciancone_marlin"
    PESSEN_INTEGRAL = "pessen_integral"
    SOME_OVERSHOOT = "some_overshoot"
    NO_OVERSHOOT = "no_overshoot"


class AutoTuneState(str, Enum):
    """Auto-tuner state machine states."""
    IDLE = "idle"
    RELAY_STEP_UP = "relay_step_up"
    RELAY_STEP_DOWN = "relay_step_down"
    CONVERGING = "converging"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PIDAutoTuner:
    """
    PID Auto-Tuner using the relay oscillation method.
    
    This class implements a state machine that applies relay control to induce
    oscillations, measures the system response, and calculates optimal PID gains.
    """
    
    def __init__(
        self,
        setpoint: float,
        output_step: float = 50.0,
        lookback_seconds: float = 60.0,
        noise_band: float = 0.5,
        sample_time: float = 1.0,
        tuning_rule: TuningRule = TuningRule.ZIEGLER_NICHOLS_PID
    ):
        """
        Initialize the PID auto-tuner.
        
        Args:
            setpoint: Target temperature for tuning
            output_step: Step size for relay (% of output range, e.g., 50.0 for 50%)
            lookback_seconds: How far back to look for peak detection
            noise_band: Temperature noise band to ignore (degrees)
            sample_time: Expected sample time in seconds
            tuning_rule: Which tuning rule to use for calculating gains
        """
        self.setpoint = setpoint
        self.output_step = output_step
        self.lookback_seconds = lookback_seconds
        self.noise_band = noise_band
        self.sample_time = sample_time
        self.tuning_rule = tuning_rule
        
        # State
        self.state = AutoTuneState.IDLE
        self.output = 0.0
        
        # Data collection
        self.inputs: List[float] = []
        self.timestamps: List[float] = []
        self.peaks: List[Tuple[float, float]] = []  # (time, value)
        self.peak_type: List[int] = []  # 1 for max, -1 for min
        
        # Results
        self.kp: Optional[float] = None
        self.ki: Optional[float] = None
        self.kd: Optional[float] = None
        self.ku: Optional[float] = None  # Ultimate gain
        self.pu: Optional[float] = None  # Ultimate period
        
        # Timing
        self.start_time: Optional[float] = None
        self.last_step_time: Optional[float] = None
        
        # Settings
        self.min_cycles = 3  # Minimum cycles to observe before calculating
        self.max_time_minutes = 30  # Maximum time to run auto-tune
        
        # Internal state
        self._last_value: Optional[float] = None
        self._peak_count = 0
        self._cycle_count = 0
        
        logger.info(f"PID AutoTuner initialized: setpoint={setpoint}, "
                   f"output_step={output_step}, tuning_rule={tuning_rule}")
    
    def start(self) -> bool:
        """
        Start the auto-tuning process.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.state != AutoTuneState.IDLE:
            logger.warning(f"Cannot start auto-tune: already in state {self.state}")
            return False
        
        # Reset all state
        self.inputs = []
        self.timestamps = []
        self.peaks = []
        self.peak_type = []
        self.kp = None
        self.ki = None
        self.kd = None
        self.ku = None
        self.pu = None
        self._last_value = None
        self._peak_count = 0
        self._cycle_count = 0
        
        self.start_time = time.time()
        self.last_step_time = self.start_time
        self.state = AutoTuneState.RELAY_STEP_UP
        self.output = self.output_step
        
        logger.info("Auto-tune started")
        return True
    
    def cancel(self):
        """Cancel the auto-tuning process."""
        if self.state not in [AutoTuneState.IDLE, AutoTuneState.SUCCEEDED, AutoTuneState.FAILED]:
            logger.info("Auto-tune cancelled")
            self.state = AutoTuneState.FAILED
            self.output = 0.0
    
    def update(self, current_value: float) -> Tuple[float, bool]:
        """
        Update the auto-tuner with a new measurement.
        
        Args:
            current_value: Current process variable (temperature)
            
        Returns:
            Tuple of (output_value, is_complete)
            - output_value: Control output (0-100%)
            - is_complete: True if tuning is complete (succeeded or failed)
        """
        if self.state in [AutoTuneState.IDLE, AutoTuneState.SUCCEEDED, AutoTuneState.FAILED]:
            return self.output, self.state in [AutoTuneState.SUCCEEDED, AutoTuneState.FAILED]
        
        current_time = time.time()
        
        # Check timeout
        if current_time - self.start_time > self.max_time_minutes * 60:
            logger.error(f"Auto-tune timeout after {self.max_time_minutes} minutes")
            self.state = AutoTuneState.FAILED
            self.output = 0.0
            return self.output, True
        
        # Store data
        self.inputs.append(current_value)
        self.timestamps.append(current_time)
        
        # Trim old data
        lookback_time = current_time - self.lookback_seconds
        while self.timestamps and self.timestamps[0] < lookback_time:
            self.timestamps.pop(0)
            self.inputs.pop(0)
        
        # Need at least 2 samples to proceed
        if len(self.inputs) < 2:
            return self.output, False
        
        # Relay control logic
        if self.state == AutoTuneState.RELAY_STEP_UP:
            if current_value > self.setpoint + self.noise_band:
                self.state = AutoTuneState.RELAY_STEP_DOWN
                self.output = 0.0
                self._detect_peak(current_time, current_value, is_max=True)
                logger.debug(f"Relay step down at temp={current_value:.2f}")
        
        elif self.state == AutoTuneState.RELAY_STEP_DOWN:
            if current_value < self.setpoint - self.noise_band:
                self.state = AutoTuneState.RELAY_STEP_UP
                self.output = self.output_step
                self._detect_peak(current_time, current_value, is_max=False)
                logger.debug(f"Relay step up at temp={current_value:.2f}")
                
                # Increment cycle count when we complete a full cycle
                self._cycle_count += 1
                
                # Check if we have enough cycles
                if self._cycle_count >= self.min_cycles:
                    if self._calculate_gains():
                        logger.info("Auto-tune succeeded!")
                        self.state = AutoTuneState.SUCCEEDED
                        self.output = 0.0
                        return self.output, True
        
        self._last_value = current_value
        return self.output, False
    
    def _detect_peak(self, peak_time: float, peak_value: float, is_max: bool):
        """
        Record a detected peak (maximum or minimum).
        
        Args:
            peak_time: Time of peak
            peak_value: Value at peak
            is_max: True if maximum peak, False if minimum
        """
        self.peaks.append((peak_time, peak_value))
        self.peak_type.append(1 if is_max else -1)
        self._peak_count += 1
        
        logger.debug(f"Peak detected: {'MAX' if is_max else 'MIN'} = {peak_value:.2f} "
                    f"at t={peak_time - self.start_time:.1f}s")
    
    def _calculate_gains(self) -> bool:
        """
        Calculate PID gains from observed oscillations.
        
        Returns:
            True if gains calculated successfully, False otherwise
        """
        if len(self.peaks) < self.min_cycles * 2:
            logger.warning(f"Not enough peaks: {len(self.peaks)} < {self.min_cycles * 2}")
            return False
        
        # Calculate average period (time between same-type peaks)
        periods = []
        for i in range(2, len(self.peaks), 2):
            period = self.peaks[i][0] - self.peaks[i-2][0]
            periods.append(period)
        
        if not periods:
            logger.error("No periods calculated")
            return False
        
        self.pu = sum(periods) / len(periods)  # Ultimate period
        logger.info(f"Ultimate period (Pu) = {self.pu:.2f} seconds")
        
        # Calculate average amplitude (peak-to-peak / 2)
        amplitudes = []
        for i in range(1, len(self.peaks)):
            if self.peak_type[i] != self.peak_type[i-1]:
                amplitude = abs(self.peaks[i][1] - self.peaks[i-1][1])
                amplitudes.append(amplitude)
        
        if not amplitudes:
            logger.error("No amplitudes calculated")
            return False
        
        avg_amplitude = sum(amplitudes) / len(amplitudes)
        logger.info(f"Average amplitude = {avg_amplitude:.2f}")
        
        # Calculate ultimate gain (Ku)
        # Ku = 4 * d / (π * a)
        # where d = output step, a = amplitude
        self.ku = (4.0 * self.output_step) / (math.pi * avg_amplitude)
        logger.info(f"Ultimate gain (Ku) = {self.ku:.4f}")
        
        # Apply tuning rules
        self._apply_tuning_rule()
        
        logger.info(f"Calculated gains: Kp={self.kp:.4f}, Ki={self.ki:.4f}, Kd={self.kd:.4f}")
        return True
    
    def _apply_tuning_rule(self):
        """Apply the selected tuning rule to calculate PID gains."""
        if self.ku is None or self.pu is None:
            logger.error("Cannot apply tuning rule: Ku or Pu is None")
            return
        
        # Ziegler-Nichols PID tuning rule
        if self.tuning_rule == TuningRule.ZIEGLER_NICHOLS_PID:
            self.kp = 0.6 * self.ku
            self.ki = 2.0 * self.kp / self.pu
            self.kd = self.kp * self.pu / 8.0
        
        # Ziegler-Nichols PI tuning rule (no derivative)
        elif self.tuning_rule == TuningRule.ZIEGLER_NICHOLS_PI:
            self.kp = 0.45 * self.ku
            self.ki = 1.2 * self.kp / self.pu
            self.kd = 0.0
        
        # Ziegler-Nichols P tuning rule (proportional only)
        elif self.tuning_rule == TuningRule.ZIEGLER_NICHOLS_P:
            self.kp = 0.5 * self.ku
            self.ki = 0.0
            self.kd = 0.0
        
        # Tyreus-Luyben tuning rule (more conservative, less overshoot)
        elif self.tuning_rule == TuningRule.TYREUS_LUYBEN:
            self.kp = 0.45 * self.ku
            self.ki = 2.2 * self.kp / self.pu
            self.kd = self.kp * self.pu / 6.3
        
        # Ciancone-Marlin tuning rule (for processes with significant lag)
        elif self.tuning_rule == TuningRule.CIANCONE_MARLIN:
            self.kp = 0.303 * self.ku
            self.ki = 0.37 * self.kp / self.pu
            self.kd = self.kp * self.pu / 1.19
        
        # Pessen Integral Rule (fast response, some overshoot)
        elif self.tuning_rule == TuningRule.PESSEN_INTEGRAL:
            self.kp = 0.7 * self.ku
            self.ki = 2.5 * self.kp / self.pu
            self.kd = 0.15 * self.kp * self.pu
        
        # Some Overshoot tuning (aggressive but stable)
        elif self.tuning_rule == TuningRule.SOME_OVERSHOOT:
            self.kp = 0.33 * self.ku
            self.ki = 2.0 * self.kp / self.pu
            self.kd = self.kp * self.pu / 3.0
        
        # No Overshoot tuning (very conservative)
        elif self.tuning_rule == TuningRule.NO_OVERSHOOT:
            self.kp = 0.2 * self.ku
            self.ki = 2.0 * self.kp / self.pu
            self.kd = self.kp * self.pu / 3.0
        
        else:
            logger.error(f"Unknown tuning rule: {self.tuning_rule}")
            # Default to Ziegler-Nichols PID
            self.kp = 0.6 * self.ku
            self.ki = 2.0 * self.kp / self.pu
            self.kd = self.kp * self.pu / 8.0
        
        logger.info(f"Applied tuning rule: {self.tuning_rule}")
    
    def get_status(self) -> dict:
        """
        Get current auto-tuner status.
        
        Returns:
            Dictionary with status information
        """
        elapsed_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            "state": self.state.value,
            "elapsed_time": elapsed_time,
            "cycle_count": self._cycle_count,
            "peak_count": self._peak_count,
            "min_cycles": self.min_cycles,
            "output": self.output,
            "setpoint": self.setpoint,
            "tuning_rule": self.tuning_rule.value,
            "results": {
                "kp": self.kp,
                "ki": self.ki,
                "kd": self.kd,
                "ku": self.ku,
                "pu": self.pu
            } if self.state == AutoTuneState.SUCCEEDED else None
        }
    
    def get_gains(self) -> Optional[Tuple[float, float, float]]:
        """
        Get the calculated PID gains.
        
        Returns:
            Tuple of (Kp, Ki, Kd) if tuning succeeded, None otherwise
        """
        if self.state == AutoTuneState.SUCCEEDED and all([self.kp, self.ki, self.kd]):
            return (self.kp, self.ki, self.kd)
        return None

