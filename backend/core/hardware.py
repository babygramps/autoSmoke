"""Hardware abstraction layer for temperature sensor and relay control."""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional, Protocol, Dict, List, Tuple, Deque
from statistics import median
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
    
    def __init__(self, pin: int = 17, active_high: bool = False, force_real: bool = False):
        self.pin = pin
        self.active_high = active_high
        self.current_state = False
        self.force_real = force_real
        self.gpio_device = None
        self._initialize_gpio()
    
    def _initialize_gpio(self):
        """Initialize GPIO for relay control."""
        try:
            # Only check environment sim_mode if not forced to use real hardware
            if not self.force_real and settings.smoker_sim_mode:
                logger.info("Simulation mode enabled, skipping GPIO initialization")
                return
            
            logger.info(f"Initializing real GPIO relay on pin {self.pin}, active_high={self.active_high}")
            from gpiozero import DigitalOutputDevice
            
            self.gpio_device = DigitalOutputDevice(
                pin=self.pin,
                active_high=self.active_high,
                initial_value=False
            )
            logger.info(f"✓ GPIO relay initialized successfully on pin {self.pin}, active_high={self.active_high}")
            
        except ImportError as e:
            logger.error(f"✗ GPIO libraries not available: {e}")
            logger.warning("Falling back to simulation mode for relay")
            self.gpio_device = None
        except Exception as e:
            logger.error(f"✗ Failed to initialize GPIO: {e}")
            logger.warning("Falling back to simulation mode for relay")
            self.gpio_device = None
    
    async def set_state(self, state: bool) -> None:
        """Set relay state."""
        if self.gpio_device is not None:
            try:
                self.gpio_device.value = state
                self.current_state = state
                logger.info(f"GPIO {self.pin}: Relay set to {'ON' if state else 'OFF'} (pin {'HIGH' if (state == self.active_high) else 'LOW'})")
            except Exception as e:
                logger.error(f"Error setting relay state on GPIO {self.pin}: {e}")
        else:
            # Simulation mode or GPIO not initialized - just log
            if state != self.current_state:
                logger.info(f"SIM Relay: {'ON' if state else 'OFF'} (GPIO device not initialized)")
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


class FilteredThermocoupleReader:
    """
    Wraps a thermocouple sensor with firmware-level filtering:
    - 5-sample median filter window
    - Outlier rejection (>8°F or >3°F/s change)
    - Double-read on suspected faults
    - Fault bit checking
    """
    
    # Filtering configuration
    WINDOW_SIZE = 5
    MAX_TEMP_JUMP_F = 8.0  # Maximum allowed temperature jump in °F
    MAX_RATE_F_PER_SEC = 3.0  # Maximum allowed rate of change in °F/s
    
    def __init__(self, sensor, thermocouple_id: int, name: str):
        self.sensor = sensor
        self.thermocouple_id = thermocouple_id
        self.name = name
        self.window: Deque[float] = deque(maxlen=self.WINDOW_SIZE)
        self.last_good_reading: Optional[float] = None
        self.last_reading_time: Optional[float] = None
        self.outliers_rejected = 0
        self.faults_detected = 0
        logger.info(f"FilteredThermocoupleReader initialized for {name} (ID={thermocouple_id})")
    
    def _c_to_f(self, temp_c: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return temp_c * 9.0 / 5.0 + 32.0
    
    def _check_fault_bits(self, sensor) -> bool:
        """Check MAX31855 fault bits (OC, SCG, SCV)."""
        try:
            # Try to access fault flags if available
            if hasattr(sensor, 'fault'):
                # Check if any fault flags are set
                if sensor.fault:
                    logger.warning(f"{self.name}: Fault bit set on MAX31855")
                    return True
            
            # Some libraries expose individual fault flags
            if hasattr(sensor, 'opencircuit') and sensor.opencircuit:
                logger.warning(f"{self.name}: Open circuit fault detected")
                return True
            if hasattr(sensor, 'shortcircuit_gnd') and sensor.shortcircuit_gnd:
                logger.warning(f"{self.name}: Short circuit to GND fault detected")
                return True
            if hasattr(sensor, 'shortcircuit_vcc') and sensor.shortcircuit_vcc:
                logger.warning(f"{self.name}: Short circuit to VCC fault detected")
                return True
                
        except Exception as e:
            logger.debug(f"{self.name}: Could not check fault bits: {e}")
        
        return False
    
    def _read_raw(self) -> Tuple[Optional[float], bool]:
        """
        Read raw temperature from sensor with fault checking.
        Returns (temp_c, has_fault)
        """
        try:
            # Check fault bits first
            if self._check_fault_bits(self.sensor):
                self.faults_detected += 1
                return (None, True)
            
            temp_c = self.sensor.temperature
            
            # Check for invalid readings
            if temp_c is None or temp_c == float('inf') or temp_c == float('-inf'):
                logger.warning(f"{self.name}: Invalid temperature reading (None or inf)")
                self.faults_detected += 1
                return (None, True)
            
            # Sanity check: reasonable temperature range (-50°C to 500°C for K-type)
            if temp_c < -50 or temp_c > 500:
                logger.warning(f"{self.name}: Temperature out of reasonable range: {temp_c:.1f}°C")
                self.faults_detected += 1
                return (None, True)
            
            return (temp_c, False)
        except Exception as e:
            logger.error(f"{self.name}: Error reading sensor: {e}")
            self.faults_detected += 1
            return (None, True)
    
    async def read_filtered(self) -> Tuple[Optional[float], bool]:
        """
        Read temperature with filtering and outlier rejection.
        Returns (temp_c, has_fault)
        """
        current_time = time.time()
        
        # First reading attempt
        temp_c, has_fault = self._read_raw()
        
        if has_fault or temp_c is None:
            # Return last good reading if we have one
            if self.last_good_reading is not None:
                logger.debug(f"{self.name}: Using last good reading due to fault: {self.last_good_reading:.1f}°C")
                return (self.last_good_reading, True)
            return (None, True)
        
        # Convert to Fahrenheit for outlier detection (more intuitive thresholds)
        temp_f = self._c_to_f(temp_c)
        
        # Outlier detection
        is_outlier = False
        
        # Check 1: Large step from last good reading
        if self.last_good_reading is not None:
            last_good_f = self._c_to_f(self.last_good_reading)
            temp_diff_f = abs(temp_f - last_good_f)
            
            if temp_diff_f > self.MAX_TEMP_JUMP_F:
                logger.warning(f"{self.name}: Large temperature jump detected: {temp_diff_f:.1f}°F (threshold: {self.MAX_TEMP_JUMP_F}°F)")
                is_outlier = True
            
            # Check 2: Rate of change
            if self.last_reading_time is not None:
                time_diff = current_time - self.last_reading_time
                if time_diff > 0:
                    rate_f_per_sec = temp_diff_f / time_diff
                    if rate_f_per_sec > self.MAX_RATE_F_PER_SEC:
                        logger.warning(f"{self.name}: High rate of change: {rate_f_per_sec:.2f}°F/s (threshold: {self.MAX_RATE_F_PER_SEC}°F/s)")
                        is_outlier = True
        
        # Double-read on suspected outlier
        if is_outlier:
            logger.info(f"{self.name}: Double-reading to verify outlier...")
            await asyncio.sleep(0.1)  # Small delay between reads
            temp_c2, has_fault2 = self._read_raw()
            
            if has_fault2 or temp_c2 is None:
                # Second read failed, discard and use last good
                self.outliers_rejected += 1
                logger.warning(f"{self.name}: Second read failed, rejecting outlier")
                if self.last_good_reading is not None:
                    return (self.last_good_reading, True)
                return (None, True)
            
            # Check if both reads agree (within 2°F)
            temp_f2 = self._c_to_f(temp_c2)
            if abs(temp_f - temp_f2) > 2.0:
                # Readings don't agree, reject
                self.outliers_rejected += 1
                logger.warning(f"{self.name}: Double-read disagreement: {temp_f:.1f}°F vs {temp_f2:.1f}°F, rejecting")
                if self.last_good_reading is not None:
                    return (self.last_good_reading, True)
                return (None, True)
            else:
                # Readings agree, use average
                temp_c = (temp_c + temp_c2) / 2.0
                temp_f = (temp_f + temp_f2) / 2.0
                logger.info(f"{self.name}: Double-read confirmed, using average: {temp_f:.1f}°F")
        
        # Add to median filter window
        self.window.append(temp_c)
        
        # Use median of window if we have enough samples
        if len(self.window) >= 3:
            filtered_temp_c = median(self.window)
        else:
            filtered_temp_c = temp_c
        
        # Update last good reading
        self.last_good_reading = filtered_temp_c
        self.last_reading_time = current_time
        
        return (filtered_temp_c, False)
    
    def get_stats(self) -> Dict[str, int]:
        """Get filtering statistics."""
        return {
            'outliers_rejected': self.outliers_rejected,
            'faults_detected': self.faults_detected,
            'window_size': len(self.window)
        }


class MultiThermocoupleManager:
    """Manages multiple MAX31855 thermocouple sensors."""
    
    def __init__(self, sim_mode: bool = False):
        self.sim_mode = sim_mode
        self.sensors: Dict[int, any] = {}  # thermocouple_id -> sensor object
        self.filtered_readers: Dict[int, FilteredThermocoupleReader] = {}  # filtered wrappers for real sensors
        self.sim_temps: Dict[int, SimTempSensor] = {}  # For simulation
        self.cs_pins_in_use: Dict[int, int] = {}  # cs_pin -> thermocouple_id mapping
        logger.info(f"MultiThermocoupleManager initialized (sim_mode={sim_mode})")
    
    def add_thermocouple(self, thermocouple_id: int, cs_pin: int, name: str):
        """Add a thermocouple to the manager."""
        logger.info(f"Adding thermocouple {name} (ID={thermocouple_id}, CS pin={cs_pin}) in {'simulation' if self.sim_mode else 'hardware'} mode")
        
        # Check for duplicate CS pin (unless in simulation mode)
        if not self.sim_mode and cs_pin in self.cs_pins_in_use:
            existing_tc_id = self.cs_pins_in_use[cs_pin]
            logger.error(f"✗ CS pin {cs_pin} already in use by thermocouple ID {existing_tc_id}")
            logger.error(f"✗ Cannot add thermocouple {name} (ID={thermocouple_id}) - duplicate CS pin")
            logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name}")
            sim_sensor = SimTempSensor()
            self.sim_temps[thermocouple_id] = sim_sensor
            return
        
        if self.sim_mode:
            # Create a simulated sensor for this thermocouple
            sim_sensor = SimTempSensor()
            sim_sensor.current_temp = 20.0 + (thermocouple_id * 5)  # Offset temps for testing
            self.sim_temps[thermocouple_id] = sim_sensor
            logger.info(f"✓ Added simulated thermocouple {name} (ID={thermocouple_id}) starting at {sim_sensor.current_temp:.1f}°C")
        else:
            # Hardware mode - try to initialize real sensor
            try:
                import board
                import digitalio
                from adafruit_max31855 import MAX31855
                
                # Map CS pin to board pin
                cs_board_pin = self._gpio_to_board_pin(cs_pin)
                if cs_board_pin is None:
                    logger.error(f"✗ Invalid CS pin {cs_pin} for thermocouple {name}")
                    logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name} (invalid pin)")
                    sim_sensor = SimTempSensor()
                    self.sim_temps[thermocouple_id] = sim_sensor
                    return
                
                logger.info(f"Attempting to initialize MAX31855 on CS pin {cs_pin}...")
                spi = board.SPI()
                cs = digitalio.DigitalInOut(cs_board_pin)
                sensor = MAX31855(spi, cs)
                
                # Test read to verify thermocouple is connected
                try:
                    temp = sensor.temperature
                    if temp is None or temp == float('inf') or temp == float('-inf'):
                        logger.error(f"✗ Thermocouple {name} initialized but returning invalid readings")
                        logger.error(f"⚠ This usually means NO THERMOCOUPLE IS CONNECTED to CS pin {cs_pin}")
                        logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name}")
                        sim_sensor = SimTempSensor()
                        self.sim_temps[thermocouple_id] = sim_sensor
                        return
                    logger.info(f"✓ Added real MAX31855 thermocouple {name} (ID={thermocouple_id}, CS pin={cs_pin}), current reading: {temp:.1f}°C")
                except Exception as read_err:
                    logger.error(f"✗ Failed to read from thermocouple {name}: {read_err}")
                    logger.error(f"⚠ This usually means NO THERMOCOUPLE IS CONNECTED to CS pin {cs_pin}")
                    logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name}")
                    sim_sensor = SimTempSensor()
                    self.sim_temps[thermocouple_id] = sim_sensor
                    return
                
                self.sensors[thermocouple_id] = sensor
                self.cs_pins_in_use[cs_pin] = thermocouple_id
                
                # Wrap sensor with filtered reader
                filtered_reader = FilteredThermocoupleReader(sensor, thermocouple_id, name)
                self.filtered_readers[thermocouple_id] = filtered_reader
                logger.info(f"✓ Created filtered reader for {name} with outlier rejection and median filtering")
                
            except ImportError as e:
                logger.error(f"✗ Required libraries not available for thermocouple {name}: {e}")
                logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name}")
                sim_sensor = SimTempSensor()
                self.sim_temps[thermocouple_id] = sim_sensor
            except Exception as e:
                logger.error(f"✗ Failed to initialize thermocouple {name}: {e}")
                logger.error(f"⚠ This might mean NO THERMOCOUPLE IS CONNECTED to CS pin {cs_pin}")
                logger.warning(f"⚠ FALLBACK: Using simulation for thermocouple {name}")
                sim_sensor = SimTempSensor()
                self.sim_temps[thermocouple_id] = sim_sensor
    
    def remove_thermocouple(self, thermocouple_id: int):
        """Remove a thermocouple from the manager."""
        # Remove from CS pin tracking
        for cs_pin, tc_id in list(self.cs_pins_in_use.items()):
            if tc_id == thermocouple_id:
                del self.cs_pins_in_use[cs_pin]
                break
        
        if thermocouple_id in self.sensors:
            del self.sensors[thermocouple_id]
        if thermocouple_id in self.filtered_readers:
            del self.filtered_readers[thermocouple_id]
        if thermocouple_id in self.sim_temps:
            del self.sim_temps[thermocouple_id]
    
    def get_fallback_status(self) -> Dict[int, str]:
        """
        Get status of which thermocouples are using fallback simulation.
        Returns dict of {thermocouple_id: 'real' | 'simulated'}
        """
        status = {}
        for tc_id in self.sensors.keys():
            status[tc_id] = 'real'
        for tc_id in self.sim_temps.keys():
            status[tc_id] = 'simulated'
        return status
    
    def has_fallback_sensors(self) -> bool:
        """Check if any sensors are using fallback simulation when not in sim_mode."""
        if self.sim_mode:
            return False  # Expected to be simulated
        return len(self.sim_temps) > 0  # Using simulation when shouldn't be
    
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
        
        # Read from real sensors using filtered readers
        for tc_id, filtered_reader in self.filtered_readers.items():
            temp_c, fault = await filtered_reader.read_filtered()
            results[tc_id] = (temp_c, fault)
            
            if not fault:
                logger.debug(f"Real TC {tc_id}: {temp_c:.1f}°C (filtered)")
            else:
                logger.debug(f"Real TC {tc_id}: FAULT (using last good: {temp_c:.1f}°C)" if temp_c else f"Real TC {tc_id}: FAULT (no data)")
        
        return results
    
    async def read_single(self, thermocouple_id: int) -> Tuple[Optional[float], bool]:
        """Read temperature from a single thermocouple. Returns (temp_c, fault)."""
        if thermocouple_id in self.sim_temps:
            temp_c = await self.sim_temps[thermocouple_id].read_temperature()
            return (temp_c, False)
        
        if thermocouple_id in self.filtered_readers:
            # Use filtered reader for real sensors
            return await self.filtered_readers[thermocouple_id].read_filtered()
        
        logger.warning(f"Thermocouple ID {thermocouple_id} not found")
        return (None, True)
    
    def get_filtering_stats(self) -> Dict[int, Dict[str, int]]:
        """
        Get filtering statistics for all thermocouples with filtered readers.
        Returns: Dict[thermocouple_id] -> stats dict
        """
        stats = {}
        for tc_id, reader in self.filtered_readers.items():
            stats[tc_id] = reader.get_stats()
        return stats
    
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
