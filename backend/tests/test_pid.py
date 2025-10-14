"""Tests for PID controller."""

import pytest
import time
from core.pid import PIDController


class TestPIDController:
    """Test PID controller functionality."""
    
    def test_pid_initialization(self):
        """Test PID controller initialization."""
        pid = PIDController(kp=1.0, ki=0.1, kd=0.5)
        assert pid.kp == 1.0
        assert pid.ki == 0.1
        assert pid.kd == 0.5
        assert pid.output_min == 0.0
        assert pid.output_max == 100.0
    
    def test_pid_compute_basic(self):
        """Test basic PID computation."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)  # P-only controller
        
        # First call should return 0 (no previous error)
        output = pid.compute(100.0, 50.0)  # setpoint=100, current=50, error=50
        assert output == 50.0  # Kp * error = 1.0 * 50 = 50
    
    def test_pid_integral_windup(self):
        """Test integral windup prevention."""
        pid = PIDController(kp=1.0, ki=1.0, kd=0.0, integral_limit=10.0)
        
        # Simulate large error for multiple iterations
        for _ in range(10):
            output = pid.compute(100.0, 0.0)  # Large error
        
        # Integral should be clamped to integral_limit
        state = pid.get_state()
        assert abs(state['integral']) <= 10.0
    
    def test_pid_output_clamping(self):
        """Test output clamping."""
        pid = PIDController(kp=10.0, ki=0.0, kd=0.0, output_min=0.0, output_max=50.0)
        
        output = pid.compute(100.0, 0.0)  # Large error
        assert output <= 50.0  # Should be clamped to max
        assert output >= 0.0   # Should be clamped to min
    
    def test_pid_bumpless_transfer(self):
        """Test bumpless transfer when gains change."""
        pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        
        # Get some output
        output1 = pid.compute(100.0, 50.0)
        
        # Change gains
        pid.set_gains(2.0, 0.0, 0.0)
        
        # Output should be continuous (bumpless transfer)
        output2 = pid.compute(100.0, 50.0)
        # The output should be similar to maintain continuity
        assert abs(output2 - output1) < 10.0  # Reasonable continuity
    
    def test_pid_derivative_action(self):
        """Test derivative action."""
        pid = PIDController(kp=0.0, ki=0.0, kd=1.0)  # D-only controller
        
        # First call - no derivative
        output1 = pid.compute(100.0, 50.0)
        
        # Second call with same error - no derivative
        time.sleep(0.1)  # Small time step
        output2 = pid.compute(100.0, 50.0)
        
        # Third call with changing error - should see derivative action
        time.sleep(0.1)
        output3 = pid.compute(100.0, 60.0)  # Error changing
        
        # Derivative should respond to error rate
        assert output3 != output2
    
    def test_pid_reset(self):
        """Test PID reset functionality."""
        pid = PIDController(kp=1.0, ki=1.0, kd=1.0)
        
        # Get some output to build up state
        pid.compute(100.0, 50.0)
        
        # Reset
        pid.reset()
        
        # State should be reset
        state = pid.get_state()
        assert state['last_error'] == 0.0
        assert state['integral'] == 0.0
        assert state['last_output'] == 0.0
        assert state['last_time'] is None
    
    def test_pid_setpoint_change(self):
        """Test setpoint change handling."""
        pid = PIDController(kp=1.0, ki=0.1, kd=0.0)
        
        # Initial setpoint
        output1 = pid.compute(100.0, 50.0)
        
        # Change setpoint
        output2 = pid.compute(200.0, 50.0)  # New setpoint
        
        # Should respond to new setpoint
        assert output2 != output1
        assert output2 > output1  # Higher setpoint should give higher output
