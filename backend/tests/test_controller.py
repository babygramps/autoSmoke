"""Tests for smoker controller."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from core.controller import SmokerController
from core.hardware import SimTempSensor, SimRelayDriver


class TestSmokerController:
    """Test smoker controller functionality."""
    
    @pytest.fixture
    def controller(self):
        """Create a controller instance for testing."""
        # Mock the hardware components
        controller = SmokerController()
        controller.temp_sensor = SimTempSensor()
        controller.relay_driver = SimRelayDriver()
        return controller
    
    @pytest.mark.asyncio
    async def test_controller_initialization(self, controller):
        """Test controller initialization."""
        assert not controller.running
        assert not controller.boost_active
        assert controller.setpoint_c == 107.2  # 225°F in Celsius
        assert controller.setpoint_f == 225.0
    
    @pytest.mark.asyncio
    async def test_setpoint_update(self, controller):
        """Test setpoint update functionality."""
        await controller.set_setpoint(250.0)
        assert controller.setpoint_f == 250.0
        assert controller.setpoint_c == 121.1  # 250°F in Celsius
    
    @pytest.mark.asyncio
    async def test_pid_gains_update(self, controller):
        """Test PID gains update."""
        await controller.set_pid_gains(5.0, 0.2, 25.0)
        assert controller.pid.kp == 5.0
        assert controller.pid.ki == 0.2
        assert controller.pid.kd == 25.0
    
    @pytest.mark.asyncio
    async def test_timing_params_update(self, controller):
        """Test timing parameters update."""
        await controller.set_timing_params(10, 15, 1.0)
        assert controller.min_on_s == 10
        assert controller.min_off_s == 15
        assert controller.hyst_c == 1.0
    
    @pytest.mark.asyncio
    async def test_boost_mode(self, controller):
        """Test boost mode functionality."""
        # Enable boost
        await controller.enable_boost(30)
        assert controller.boost_active
        assert controller.boost_until is not None
        
        # Disable boost
        await controller.disable_boost()
        assert not controller.boost_active
        assert controller.boost_until is None
    
    def test_pid_to_boolean_hysteresis(self, controller):
        """Test PID to boolean conversion with hysteresis."""
        controller.setpoint_c = 100.0
        controller.hyst_c = 2.0
        
        # Test hysteresis behavior
        # Currently OFF, temp below setpoint - hysteresis should turn ON
        controller.output_bool = False
        result = controller._pid_to_boolean(97.0)  # Below setpoint - hysteresis
        assert result is True
        
        # Currently ON, temp above setpoint + hysteresis should turn OFF
        controller.output_bool = True
        result = controller._pid_to_boolean(103.0)  # Above setpoint + hysteresis
        assert result is False
        
        # Currently ON, temp within hysteresis band should stay ON
        controller.output_bool = True
        result = controller._pid_to_boolean(101.0)  # Within hysteresis
        assert result is True
    
    def test_min_timing_constraints(self, controller):
        """Test minimum on/off timing constraints."""
        controller.min_on_s = 5
        controller.min_off_s = 3
        
        # Mock time
        import time
        current_time = 1000.0
        
        # Test min on time
        controller.last_on_time = current_time - 2  # Only 2 seconds ago
        controller.output_bool = False  # Want to turn OFF
        controller.relay_state = True   # Currently ON
        
        # Should not allow turning OFF yet
        assert (current_time - controller.last_on_time) < controller.min_on_s
        
        # Test min off time
        controller.last_off_time = current_time - 1  # Only 1 second ago
        controller.output_bool = True   # Want to turn ON
        controller.relay_state = False  # Currently OFF
        
        # Should not allow turning ON yet
        assert (current_time - controller.last_off_time) < controller.min_off_s
    
    @pytest.mark.asyncio
    async def test_controller_start_stop(self, controller):
        """Test controller start/stop functionality."""
        # Start controller
        await controller.start()
        assert controller.running
        
        # Stop controller
        await controller.stop()
        assert not controller.running
        assert not controller.relay_state  # Relay should be OFF when stopped
    
    def test_get_status(self, controller):
        """Test status retrieval."""
        status = controller.get_status()
        
        assert 'running' in status
        assert 'boost_active' in status
        assert 'current_temp_c' in status
        assert 'setpoint_c' in status
        assert 'pid_output' in status
        assert 'relay_state' in status
        assert 'loop_count' in status
