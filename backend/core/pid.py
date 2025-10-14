"""PID controller implementation with anti-windup and bumpless transfer."""

import time
from typing import Optional


class PIDController:
    """Discrete PID controller with anti-windup and bumpless transfer."""
    
    def __init__(
        self,
        kp: float = 4.0,
        ki: float = 0.1,
        kd: float = 20.0,
        output_min: float = 0.0,
        output_max: float = 100.0,
        integral_limit: float = 100.0
    ):
        """
        Initialize PID controller.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            output_min: Minimum output value
            output_max: Maximum output value
            integral_limit: Maximum integral term to prevent windup
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        
        # Internal state
        self._last_error = 0.0
        self._integral = 0.0
        self._last_time = None
        self._last_output = 0.0
        
        # Bumpless transfer state
        self._last_setpoint = None
        self._last_gains = None
    
    def compute(self, setpoint: float, current_value: float) -> float:
        """
        Compute PID output.
        
        Args:
            setpoint: Target value
            current_value: Current measured value
            
        Returns:
            PID output (0-100%)
        """
        current_time = time.time()
        
        # Handle first call
        if self._last_time is None:
            self._last_time = current_time
            self._last_setpoint = setpoint
            self._last_gains = (self.kp, self.ki, self.kd)
            return self._last_output
        
        # Calculate time delta
        dt = current_time - self._last_time
        if dt <= 0:
            return self._last_output
        
        # Calculate error
        error = setpoint - current_value
        
        # Check for bumpless transfer (setpoint or gains changed)
        if (self._last_setpoint != setpoint or 
            self._last_gains != (self.kp, self.ki, self.kd)):
            self._bumpless_transfer(setpoint, current_value, error)
            self._last_setpoint = setpoint
            self._last_gains = (self.kp, self.ki, self.kd)
        
        # Proportional term
        proportional = self.kp * error
        
        # Integral term with anti-windup
        self._integral += error * dt
        # Clamp integral to prevent windup
        self._integral = max(-self.integral_limit, min(self.integral_limit, self._integral))
        integral = self.ki * self._integral
        
        # Derivative term
        derivative = self.kd * (error - self._last_error) / dt
        
        # Calculate output
        output = proportional + integral + derivative
        
        # Clamp output
        output = max(self.output_min, min(self.output_max, output))
        
        # Update state
        self._last_error = error
        self._last_time = current_time
        self._last_output = output
        
        return output
    
    def _bumpless_transfer(self, setpoint: float, current_value: float, error: float):
        """
        Implement bumpless transfer when setpoint or gains change.
        
        This prevents sudden output changes by adjusting the integral term
        to maintain continuity.
        """
        # Calculate what the output would be with new parameters
        new_proportional = self.kp * error
        new_derivative = self.kd * (error - self._last_error) if self._last_error != 0 else 0
        
        # Adjust integral to maintain output continuity
        desired_integral = self._last_output - new_proportional - new_derivative
        self._integral = desired_integral / self.ki if self.ki != 0 else 0
        
        # Clamp integral to prevent windup
        self._integral = max(-self.integral_limit, min(self.integral_limit, self._integral))
    
    def reset(self):
        """Reset PID controller state."""
        self._last_error = 0.0
        self._integral = 0.0
        self._last_time = None
        self._last_output = 0.0
        self._last_setpoint = None
        self._last_gains = None
    
    def set_gains(self, kp: float, ki: float, kd: float):
        """Update PID gains (triggers bumpless transfer)."""
        self.kp = kp
        self.ki = ki
        self.kd = kd
    
    def get_state(self) -> dict:
        """Get current PID state for debugging."""
        return {
            "kp": self.kp,
            "ki": self.ki,
            "kd": self.kd,
            "last_error": self._last_error,
            "integral": self._integral,
            "last_output": self._last_output,
            "output_min": self.output_min,
            "output_max": self.output_max
        }
