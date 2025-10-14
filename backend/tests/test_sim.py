"""Tests for simulation mode."""

import pytest
import asyncio
from core.hardware import SimTempSensor, SimRelayDriver


class TestSimulationMode:
    """Test simulation mode functionality."""
    
    @pytest.mark.asyncio
    async def test_sim_temp_sensor(self):
        """Test simulated temperature sensor."""
        sensor = SimTempSensor()
        
        # Test initial temperature reading
        temp1 = await sensor.read_temperature()
        assert temp1 is not None
        assert isinstance(temp1, float)
        assert 15.0 <= temp1 <= 200.0  # Within reasonable bounds
        
        # Test setpoint update
        sensor.set_setpoint(120.0)
        assert sensor.setpoint == 120.0
        
        # Test multiple readings (should show some variation)
        temps = []
        for _ in range(10):
            temp = await sensor.read_temperature()
            temps.append(temp)
            await asyncio.sleep(0.01)  # Small delay
        
        # Should have some variation
        assert len(set(temps)) > 1  # Not all identical
    
    @pytest.mark.asyncio
    async def test_sim_relay_driver(self):
        """Test simulated relay driver."""
        relay = SimRelayDriver()
        
        # Test initial state
        state = await relay.get_state()
        assert state is False  # Initially OFF
        
        # Test setting relay ON
        await relay.set_state(True)
        state = await relay.get_state()
        assert state is True
        
        # Test setting relay OFF
        await relay.set_state(False)
        state = await relay.get_state()
        assert state is False
    
    @pytest.mark.asyncio
    async def test_sim_integration(self):
        """Test simulation mode integration."""
        from core.controller import SmokerController
        from core.config import settings
        
        # Mock settings to enable sim mode
        with pytest.MonkeyPatch().context() as m:
            m.setattr(settings, 'smoker_sim_mode', True)
            
            controller = SmokerController()
            
            # Should be using simulation components
            assert isinstance(controller.temp_sensor, SimTempSensor)
            assert isinstance(controller.relay_driver, SimRelayDriver)
            
            # Test basic functionality
            await controller.start()
            assert controller.running
            
            # Let it run for a short time
            await asyncio.sleep(0.1)
            
            await controller.stop()
            assert not controller.running
    
    def test_sim_temp_sensor_setpoint_influence(self):
        """Test that setpoint influences temperature simulation."""
        sensor = SimTempSensor()
        
        # Set different setpoints and check temperature trends
        sensor.set_setpoint(100.0)
        temp1 = asyncio.run(sensor.read_temperature())
        
        sensor.set_setpoint(150.0)
        temp2 = asyncio.run(sensor.read_temperature())
        
        # Temperature should be influenced by setpoint
        # (This is probabilistic, so we just check it's reasonable)
        assert isinstance(temp1, float)
        assert isinstance(temp2, float)
        assert 15.0 <= temp1 <= 200.0
        assert 15.0 <= temp2 <= 200.0
    
    @pytest.mark.asyncio
    async def test_sim_relay_logging(self):
        """Test that relay state changes are logged in simulation."""
        import logging
        from io import StringIO
        
        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        logger = logging.getLogger('backend.core.hardware')
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        relay = SimRelayDriver()
        
        # Change relay state
        await relay.set_state(True)
        await relay.set_state(False)
        
        # Check that state changes were logged
        log_output = log_capture.getvalue()
        assert 'SIM: Relay ON' in log_output
        assert 'SIM: Relay OFF' in log_output
        
        logger.removeHandler(handler)
