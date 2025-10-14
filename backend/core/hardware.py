"""Hardware abstraction layer for temperature sensor and relay control."""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional, Protocol
from core.config import settings

logger = logging.getLogger(__name__)


class TempSensor(Protocol):
    """Protocol for temperature sensors."""
    
    async def read_temperature(self) -> Optional[float]:
        """Read temperature in Celsius. Returns None on error."""
        ...


class RelayDriver(Protocol):
    """Protocol for relay drivers."""
    
    async def set_state(self, state: bool) -> None:
        """Set relay state (True = ON, False = OFF)."""
        ...
    
    async def get_state(self) -> bool:
        """Get current relay state."""
        ...


class RealTempSensor:
    """Real MAX31855 thermocouple sensor via SPI."""
    
    def __init__(self):
        self.sensor = None
        self._initialize_sensor()
    
    def _initialize_sensor(self):
        """Initialize the MAX31855 sensor."""
        try:
            if settings.smoker_sim_mode:
                logger.info("Simulation mode enabled, skipping real sensor initialization")
                return
                
            import board
            import digitalio
            from adafruit_max31855 import MAX31855
            
            # SPI configuration for MAX31855
            spi = board.SPI()
            cs = digitalio.DigitalInOut(board.D5)  # CE0 pin
            self.sensor = MAX31855(spi, cs)
            logger.info("MAX31855 sensor initialized successfully")
            
        except ImportError as e:
            logger.error(f"Required libraries not available: {e}")
            logger.info("Falling back to simulation mode")
            self.sensor = None
        except Exception as e:
            logger.error(f"Failed to initialize MAX31855 sensor: {e}")
            logger.info("Falling back to simulation mode")
            self.sensor = None
    
    async def read_temperature(self) -> Optional[float]:
        """Read temperature from MAX31855 sensor."""
        if self.sensor is None:
            return None
            
        try:
            # Read temperature in Celsius
            temp_c = self.sensor.temperature
            if temp_c is None or temp_c == float('inf') or temp_c == float('-inf'):
                logger.warning("Invalid temperature reading from sensor")
                return None
            return temp_c
        except Exception as e:
            logger.error(f"Error reading temperature: {e}")
            return None


class SimTempSensor:
    """Simulated temperature sensor with random walk around setpoint."""
    
    def __init__(self):
        self.current_temp = 20.0  # Start at 20°C
        self.setpoint = 107.2  # 225°F in Celsius
        self.noise_std = 0.5  # Temperature noise standard deviation
        self.drift_rate = 0.1  # Temperature drift per second
        self.last_update = time.time()
    
    async def read_temperature(self) -> Optional[float]:
        """Simulate temperature reading with random walk."""
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # Random walk towards setpoint with some noise
        error = self.setpoint - self.current_temp
        drift = error * 0.01 * dt  # Slow drift towards setpoint
        noise = random.gauss(0, self.noise_std)
        
        self.current_temp += drift + noise
        
        # Add some realistic bounds
        self.current_temp = max(15.0, min(200.0, self.current_temp))
        
        return self.current_temp
    
    def set_setpoint(self, setpoint_c: float):
        """Update the setpoint for simulation."""
        self.setpoint = setpoint_c


class RealRelayDriver:
    """Real GPIO relay driver."""
    
    def __init__(self, pin: int = 17, active_high: bool = False):
        self.pin = pin
        self.active_high = active_high
        self.current_state = False
        self._initialize_gpio()
    
    def _initialize_gpio(self):
        """Initialize GPIO for relay control."""
        try:
            if settings.smoker_sim_mode:
                logger.info("Simulation mode enabled, skipping GPIO initialization")
                return
                
            from gpiozero import DigitalOutputDevice
            
            self.gpio_device = DigitalOutputDevice(
                pin=self.pin,
                active_high=self.active_high,
                initial_value=False
            )
            logger.info(f"GPIO relay initialized on pin {self.pin}, active_high={self.active_high}")
            
        except ImportError as e:
            logger.error(f"GPIO libraries not available: {e}")
            logger.info("Falling back to simulation mode")
            self.gpio_device = None
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            logger.info("Falling back to simulation mode")
            self.gpio_device = None
    
    async def set_state(self, state: bool) -> None:
        """Set relay state."""
        if self.gpio_device is not None:
            try:
                self.gpio_device.value = state
                self.current_state = state
                logger.debug(f"Relay set to {'ON' if state else 'OFF'}")
            except Exception as e:
                logger.error(f"Error setting relay state: {e}")
        else:
            # Simulation mode - just log
            if state != self.current_state:
                logger.info(f"SIM: Relay {'ON' if state else 'OFF'}")
                self.current_state = state
    
    async def get_state(self) -> bool:
        """Get current relay state."""
        if self.gpio_device is not None:
            try:
                return self.gpio_device.value
            except Exception as e:
                logger.error(f"Error reading relay state: {e}")
                return self.current_state
        return self.current_state


class SimRelayDriver:
    """Simulated relay driver."""
    
    def __init__(self):
        self.current_state = False
        logger.info("Simulated relay driver initialized")
    
    async def set_state(self, state: bool) -> None:
        """Simulate relay state change."""
        if state != self.current_state:
            logger.info(f"SIM: Relay {'ON' if state else 'OFF'}")
            self.current_state = state
    
    async def get_state(self) -> bool:
        """Get simulated relay state."""
        return self.current_state


def create_temp_sensor() -> TempSensor:
    """Create temperature sensor based on configuration."""
    if settings.smoker_sim_mode:
        return SimTempSensor()
    else:
        return RealTempSensor()


def create_relay_driver() -> RelayDriver:
    """Create relay driver based on configuration."""
    if settings.smoker_sim_mode:
        return SimRelayDriver()
    else:
        return RealRelayDriver(
            pin=settings.smoker_gpio_pin,
            active_high=settings.smoker_relay_active_high
        )
