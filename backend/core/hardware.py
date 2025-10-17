"""Hardware abstraction layer for temperature sensor and relay control."""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional, Protocol, Dict, List, Tuple
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


class MultiThermocoupleManager:
    """Manages multiple MAX31855 thermocouple sensors."""
    
    def __init__(self, sim_mode: bool = False):
        self.sim_mode = sim_mode
        self.sensors: Dict[int, any] = {}  # thermocouple_id -> sensor object
        self.sim_temps: Dict[int, SimTempSensor] = {}  # For simulation
        logger.info(f"MultiThermocoupleManager initialized (sim_mode={sim_mode})")
    
    def add_thermocouple(self, thermocouple_id: int, cs_pin: int, name: str):
        """Add a thermocouple to the manager."""
        logger.info(f"Adding thermocouple {name} (ID={thermocouple_id}, CS pin={cs_pin}) in {'simulation' if self.sim_mode else 'hardware'} mode")
        
        if self.sim_mode:
            # Create a simulated sensor for this thermocouple
            sim_sensor = SimTempSensor()
            sim_sensor.current_temp = 20.0 + (thermocouple_id * 5)  # Offset temps for testing
            self.sim_temps[thermocouple_id] = sim_sensor
            logger.info(f"✓ Added simulated thermocouple {name} (ID={thermocouple_id}) starting at {sim_sensor.current_temp:.1f}°C")
        else:
            try:
                import board
                import digitalio
                from adafruit_max31855 import MAX31855
                
                # Map CS pin to board pin
                cs_board_pin = self._gpio_to_board_pin(cs_pin)
                if cs_board_pin is None:
                    logger.error(f"✗ Invalid CS pin {cs_pin} for thermocouple {name}")
                    logger.warning(f"Falling back to simulation mode for thermocouple {name}")
                    sim_sensor = SimTempSensor()
                    self.sim_temps[thermocouple_id] = sim_sensor
                    return
                
                spi = board.SPI()
                cs = digitalio.DigitalInOut(cs_board_pin)
                sensor = MAX31855(spi, cs)
                self.sensors[thermocouple_id] = sensor
                logger.info(f"✓ Added real MAX31855 thermocouple {name} (ID={thermocouple_id}, CS pin={cs_pin})")
                
            except ImportError as e:
                logger.error(f"✗ Required libraries not available for thermocouple {name}: {e}")
                logger.warning(f"Falling back to simulation mode for thermocouple {name}")
                # Fall back to simulation for this sensor
                sim_sensor = SimTempSensor()
                self.sim_temps[thermocouple_id] = sim_sensor
            except Exception as e:
                logger.error(f"✗ Failed to initialize thermocouple {name}: {e}")
                logger.warning(f"Falling back to simulation mode for thermocouple {name}")
                sim_sensor = SimTempSensor()
                self.sim_temps[thermocouple_id] = sim_sensor
    
    def remove_thermocouple(self, thermocouple_id: int):
        """Remove a thermocouple from the manager."""
        if thermocouple_id in self.sensors:
            del self.sensors[thermocouple_id]
        if thermocouple_id in self.sim_temps:
            del self.sim_temps[thermocouple_id]
    
    def update_setpoint(self, setpoint_c: float):
        """Update setpoint for all simulation sensors."""
        for sim_sensor in self.sim_temps.values():
            sim_sensor.set_setpoint(setpoint_c)
    
    async def read_all(self) -> Dict[int, Tuple[Optional[float], bool]]:
        """
        Read temperatures from all thermocouples.
        Returns: Dict[thermocouple_id] -> (temp_c, fault)
        """
        results = {}
        
        logger.debug(f"Reading all thermocouples: {len(self.sim_temps)} simulated, {len(self.sensors)} real")
        
        if self.sim_mode or self.sim_temps:
            # Read from simulated sensors
            for tc_id, sim_sensor in self.sim_temps.items():
                temp_c = await sim_sensor.read_temperature()
                results[tc_id] = (temp_c, False)  # No faults in simulation
                logger.debug(f"Simulated TC {tc_id}: {temp_c:.1f}°C")
        
        # Read from real sensors
        for tc_id, sensor in self.sensors.items():
            try:
                temp_c = sensor.temperature
                fault = False
                
                # Check for invalid readings
                if temp_c is None or temp_c == float('inf') or temp_c == float('-inf'):
                    logger.warning(f"Invalid temperature reading from thermocouple ID {tc_id}")
                    temp_c = None
                    fault = True
                else:
                    logger.debug(f"Real TC {tc_id}: {temp_c:.1f}°C")
                
                results[tc_id] = (temp_c, fault)
            except Exception as e:
                logger.error(f"Error reading thermocouple ID {tc_id}: {e}")
                results[tc_id] = (None, True)
        
        return results
    
    async def read_single(self, thermocouple_id: int) -> Tuple[Optional[float], bool]:
        """Read temperature from a single thermocouple. Returns (temp_c, fault)."""
        if thermocouple_id in self.sim_temps:
            temp_c = await self.sim_temps[thermocouple_id].read_temperature()
            return (temp_c, False)
        
        if thermocouple_id in self.sensors:
            try:
                sensor = self.sensors[thermocouple_id]
                temp_c = sensor.temperature
                fault = False
                
                if temp_c is None or temp_c == float('inf') or temp_c == float('-inf'):
                    logger.warning(f"Invalid temperature reading from thermocouple ID {thermocouple_id}")
                    return (None, True)
                
                return (temp_c, fault)
            except Exception as e:
                logger.error(f"Error reading thermocouple ID {thermocouple_id}: {e}")
                return (None, True)
        
        logger.warning(f"Thermocouple ID {thermocouple_id} not found")
        return (None, True)
    
    def _gpio_to_board_pin(self, gpio_num: int):
        """Map GPIO number to board pin. Returns board.D<num> or None."""
        try:
            import board
            # Common GPIO to board pin mappings for Raspberry Pi
            gpio_map = {
                5: board.D5,   # CE1
                8: board.D8,   # CE0
                7: board.D7,   # GPIO7
                24: board.D24, # GPIO24
                25: board.D25, # GPIO25
                22: board.D22, # GPIO22
                23: board.D23, # GPIO23
                17: board.D17, # GPIO17
                27: board.D27, # GPIO27
            }
            return gpio_map.get(gpio_num)
        except ImportError:
            return None


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
