"""Main smoker controller with PID loop and relay control."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings, ControlMode
from core.hardware import create_temp_sensor, create_relay_driver, SimTempSensor, MultiThermocoupleManager
from core.pid import PIDController
from core.alerts import alert_manager
from db.models import Smoke, Reading, Event, Settings as DBSettings, Thermocouple, ThermocoupleReading, CONTROL_MODE_THERMOSTAT, CONTROL_MODE_TIME_PROPORTIONAL
from db.session import get_session_sync

logger = logging.getLogger(__name__)


class SmokerController:
    """Main smoker controller managing PID loop and relay control."""
    
    def __init__(self):
        self.running = False
        self.boost_active = False
        self.boost_until = None
        
        # Hardware
        self.temp_sensor = create_temp_sensor()  # Kept for backward compatibility
        self.relay_driver = create_relay_driver()
        
        # Multi-thermocouple manager
        self.tc_manager = MultiThermocoupleManager(sim_mode=settings.smoker_sim_mode)
        self.control_tc_id = None  # ID of the control thermocouple
        self.tc_readings = {}  # Latest readings: {tc_id: (temp_c, fault)}
        
        # Load settings from database (or use defaults)
        db_settings = self._load_db_settings()
        
        # PID Controller
        self.pid = PIDController(
            kp=db_settings.kp if db_settings else settings.smoker_pid_kp,
            ki=db_settings.ki if db_settings else settings.smoker_pid_ki,
            kd=db_settings.kd if db_settings else settings.smoker_pid_kd
        )
        
        # Control mode
        if db_settings:
            self.control_mode = db_settings.control_mode
        else:
            self.control_mode = settings.smoker_control_mode
        
        # Control state
        if db_settings:
            self.setpoint_c = db_settings.setpoint_c
            self.setpoint_f = db_settings.setpoint_f
        else:
            self.setpoint_c = settings.get_setpoint_celsius()
            self.setpoint_f = settings.get_setpoint_fahrenheit()
        
        # Load thermocouples from database (after setpoint is initialized)
        self._load_thermocouples()
        
        self.current_temp_c = None
        self.current_temp_f = None
        self.pid_output = 0.0
        self.relay_state = False
        self.output_bool = False
        
        # Timing control
        self.last_on_time = None
        self.last_off_time = None
        self.min_on_s = db_settings.min_on_s if db_settings else settings.smoker_min_on_s
        self.min_off_s = db_settings.min_off_s if db_settings else settings.smoker_min_off_s
        self.hyst_c = db_settings.hyst_c if db_settings else settings.smoker_hyst_c
        self.time_window_s = db_settings.time_window_s if db_settings else settings.smoker_time_window_s
        
        # Time-proportional control state
        self.window_start_time = None
        self.window_on_duration = 0.0
        
        # Active smoking session
        self.active_smoke_id = None
        self._load_active_smoke()
        
        # Control loop task
        self._control_task = None
        self._loop_interval = 1.0  # 1 Hz
        
        # Statistics
        self.loop_count = 0
        self.last_loop_time = None
        
        logger.info("SmokerController initialized")
    
    def _load_db_settings(self):
        """Load settings from database, or return None if not found."""
        try:
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                if db_settings:
                    logger.info("Loaded settings from database")
                    return db_settings
                else:
                    logger.info("No database settings found, using config defaults")
                    return None
        except Exception as e:
            logger.warning(f"Failed to load database settings: {e}. Using config defaults.")
            return None
    
    def _load_thermocouples(self):
        """Load thermocouple configurations from database and initialize hardware."""
        try:
            with get_session_sync() as session:
                from sqlmodel import select
                # Get all enabled thermocouples
                statement = select(Thermocouple).where(Thermocouple.enabled == True).order_by(Thermocouple.order)
                thermocouples = session.exec(statement).all()
                
                if not thermocouples:
                    logger.warning("No thermocouples configured in database")
                    return
                
                # Add each thermocouple to the manager
                for tc in thermocouples:
                    self.tc_manager.add_thermocouple(tc.id, tc.cs_pin, tc.name)
                    if tc.is_control:
                        self.control_tc_id = tc.id
                        logger.info(f"Control thermocouple set to: {tc.name} (ID={tc.id})")
                
                if self.control_tc_id is None and thermocouples:
                    # No control thermocouple set, use the first one
                    self.control_tc_id = thermocouples[0].id
                    logger.warning(f"No control thermocouple specified, using first: {thermocouples[0].name}")
                
                logger.info(f"Loaded {len(thermocouples)} thermocouple(s)")
                
                # Update simulation sensors with current setpoint
                if settings.smoker_sim_mode:
                    self.tc_manager.update_setpoint(self.setpoint_c)
                
        except Exception as e:
            logger.error(f"Failed to load thermocouples: {e}")
    
    def reload_thermocouples(self):
        """Reload thermocouple configuration (call after DB changes)."""
        # Clear existing thermocouples
        self.tc_readings = {}
        # Reload from DB
        self._load_thermocouples()
    
    def _load_active_smoke(self):
        """Load or create active smoking session."""
        try:
            with get_session_sync() as session:
                # Find active smoke session
                from sqlmodel import select
                statement = select(Smoke).where(Smoke.is_active == True)
                active_smoke = session.exec(statement).first()
                
                if active_smoke:
                    self.active_smoke_id = active_smoke.id
                    logger.info(f"Loaded active smoke session: {active_smoke.name} (ID: {active_smoke.id})")
                else:
                    logger.info("No active smoke session found")
        except Exception as e:
            logger.warning(f"Failed to load active smoke: {e}")
            self.active_smoke_id = None
    
    def set_active_smoke(self, smoke_id: int):
        """Set the active smoking session."""
        self.active_smoke_id = smoke_id
        logger.info(f"Active smoke session set to ID: {smoke_id}")
    
    async def start(self):
        """Start the control loop."""
        if self.running:
            logger.warning("Controller already running")
            return
        
        self.running = True
        self._control_task = asyncio.create_task(self._control_loop())
        
        # Log startup event
        await self._log_event("controller_start", "Controller started")
        logger.info("Smoker controller started")
    
    async def stop(self):
        """Stop the control loop."""
        if not self.running:
            logger.warning("Controller not running")
            return
        
        self.running = False
        
        # Turn off relay
        await self.relay_driver.set_state(False)
        self.relay_state = False
        
        # Cancel control task
        if self._control_task:
            self._control_task.cancel()
            try:
                await self._control_task
            except asyncio.CancelledError:
                pass
            self._control_task = None
        
        # Log shutdown event
        await self._log_event("controller_stop", "Controller stopped")
        logger.info("Smoker controller stopped")
    
    async def set_setpoint(self, setpoint_f: float):
        """Update setpoint temperature."""
        old_setpoint_f = self.setpoint_f
        self.setpoint_f = setpoint_f
        self.setpoint_c = settings.fahrenheit_to_celsius(setpoint_f)
        
        # Update simulation sensor if in sim mode
        if isinstance(self.temp_sensor, SimTempSensor):
            self.temp_sensor.set_setpoint(self.setpoint_c)
        
        # Update all thermocouple simulation sensors
        self.tc_manager.update_setpoint(self.setpoint_c)
        
        # Log setpoint change
        await self._log_event(
            "setpoint_change", 
            f"Setpoint changed from {old_setpoint_f:.1f}°F to {setpoint_f:.1f}°F"
        )
        
        logger.info(f"Setpoint updated to {setpoint_f:.1f}°F ({self.setpoint_c:.1f}°C)")
    
    async def set_pid_gains(self, kp: float, ki: float, kd: float):
        """Update PID gains."""
        self.pid.set_gains(kp, ki, kd)
        await self._log_event(
            "pid_gains_change",
            f"PID gains updated: Kp={kp}, Ki={ki}, Kd={kd}"
        )
        logger.info(f"PID gains updated: Kp={kp}, Ki={ki}, Kd={kd}")
    
    async def set_timing_params(self, min_on_s: int, min_off_s: int, hyst_c: float, time_window_s: int = None):
        """Update timing parameters."""
        self.min_on_s = min_on_s
        self.min_off_s = min_off_s
        self.hyst_c = hyst_c
        if time_window_s is not None:
            self.time_window_s = time_window_s
        
        await self._log_event(
            "timing_params_change",
            f"Timing updated: min_on={min_on_s}s, min_off={min_off_s}s, hyst={hyst_c:.1f}°C, window={self.time_window_s}s"
        )
        logger.info(f"Timing parameters updated: min_on={min_on_s}s, min_off={min_off_s}s, hyst={hyst_c:.1f}°C, window={self.time_window_s}s")
    
    async def set_control_mode(self, mode: str):
        """Update control mode."""
        old_mode = self.control_mode
        self.control_mode = mode
        
        # Reset PID when switching modes
        if old_mode != mode:
            self.pid.reset()
            self.window_start_time = None
            self.window_on_duration = 0.0
        
        await self._log_event(
            "control_mode_change",
            f"Control mode changed from {old_mode} to {mode}"
        )
        logger.info(f"Control mode changed from {old_mode} to {mode}")
    
    async def enable_boost(self, duration_s: int = None):
        """Enable boost mode for specified duration."""
        if duration_s is None:
            duration_s = settings.smoker_boost_duration_s
        
        self.boost_active = True
        self.boost_until = datetime.utcnow() + timedelta(seconds=duration_s)
        
        await self._log_event(
            "boost_enabled",
            f"Boost mode enabled for {duration_s} seconds"
        )
        logger.info(f"Boost mode enabled for {duration_s} seconds")
    
    async def disable_boost(self):
        """Disable boost mode."""
        self.boost_active = False
        self.boost_until = None
        
        await self._log_event("boost_disabled", "Boost mode disabled")
        logger.info("Boost mode disabled")
    
    async def _control_loop(self):
        """Main control loop running at 1 Hz."""
        while self.running:
            loop_start = time.time()
            
            try:
                await self._control_iteration()
            except Exception as e:
                logger.error(f"Error in control loop iteration: {e}")
                # Continue running even if one iteration fails
            
            # Calculate loop timing
            loop_time = time.time() - loop_start
            self.last_loop_time = loop_time
            
            # Sleep for remaining time to maintain 1 Hz
            sleep_time = max(0, self._loop_interval - loop_time)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            
            self.loop_count += 1
    
    async def _control_iteration(self):
        """Single control loop iteration."""
        # Read temperatures from all thermocouples
        self.tc_readings = await self.tc_manager.read_all()
        
        # Get control thermocouple temperature
        control_temp_c = None
        control_fault = True
        
        if self.control_tc_id and self.control_tc_id in self.tc_readings:
            control_temp_c, control_fault = self.tc_readings[self.control_tc_id]
        
        if control_temp_c is None or control_fault:
            # Control sensor fault - turn off relay and log error
            await self.relay_driver.set_state(False)
            self.relay_state = False
            self.output_bool = False
            
            await self._log_event("sensor_fault", f"Control thermocouple reading failed (ID={self.control_tc_id})")
            logger.error(f"Control thermocouple reading failed (ID={self.control_tc_id})")
            return
        
        # Update temperature values (for backward compatibility and status)
        self.current_temp_c = control_temp_c
        self.current_temp_f = settings.celsius_to_fahrenheit(control_temp_c)
        temp_c = control_temp_c
        
        # Check if boost mode should end
        if self.boost_active and self.boost_until and datetime.utcnow() >= self.boost_until:
            await self.disable_boost()
        
        # Determine relay state
        if self.boost_active:
            # Boost mode - force relay ON
            self.output_bool = True
            await self._set_relay_state(True)
        else:
            # Normal control based on mode
            if self.control_mode == CONTROL_MODE_THERMOSTAT:
                # Thermostat mode - simple on/off with hysteresis
                await self._thermostat_control(temp_c)
            else:
                # Time-proportional mode - PID with duty cycle control
                await self._time_proportional_control(temp_c)
        
        # Log reading to database
        await self._log_reading()
        
        # Check alerts
        await alert_manager.check_alerts(self.get_status())
    
    async def _thermostat_control(self, temp_c: float):
        """
        Thermostat control mode - simple on/off with hysteresis.
        No PID involved, just temperature-based switching.
        """
        # Determine desired state based on hysteresis
        if self.output_bool:
            # Currently ON - turn OFF when temp exceeds setpoint + hysteresis
            self.output_bool = temp_c < (self.setpoint_c + self.hyst_c)
        else:
            # Currently OFF - turn ON when temp drops below setpoint - hysteresis
            self.output_bool = temp_c < (self.setpoint_c - self.hyst_c)
        
        # Set PID output to 0 or 100 for logging consistency
        self.pid_output = 100.0 if self.output_bool else 0.0
        
        # Apply relay state with timing constraints
        await self._apply_relay_with_timing(self.output_bool)
    
    async def _time_proportional_control(self, temp_c: float):
        """
        Time-proportional control mode - uses PID output to control duty cycle.
        PID outputs 0-100%, which determines ON time within a time window.
        
        Example: If PID output is 60% and time window is 10s,
        relay is ON for 6s and OFF for 4s in each 10s window.
        """
        # Compute PID output (0-100%)
        self.pid_output = self.pid.compute(self.setpoint_c, temp_c)
        
        now = time.time()
        
        # Initialize window if needed
        if self.window_start_time is None:
            self.window_start_time = now
            # Calculate ON duration for this window
            self.window_on_duration = (self.pid_output / 100.0) * self.time_window_s
        
        # Check if we're in a new window
        elapsed = now - self.window_start_time
        if elapsed >= self.time_window_s:
            # Start new window
            self.window_start_time = now
            self.window_on_duration = (self.pid_output / 100.0) * self.time_window_s
            elapsed = 0
        
        # Determine if relay should be ON in this window
        if elapsed < self.window_on_duration:
            self.output_bool = True
        else:
            self.output_bool = False
        
        # Apply relay state (no min on/off timing for time-proportional mode)
        await self._set_relay_state(self.output_bool)
    
    async def _apply_relay_with_timing(self, desired_state: bool):
        """Apply relay control with minimum on/off timing (for thermostat mode)."""
        now = time.time()
        
        # Check minimum timing constraints
        if desired_state and not self.relay_state:
            # Want to turn ON
            if self.last_off_time and (now - self.last_off_time) < self.min_off_s:
                # Haven't been off long enough
                return
            await self._set_relay_state(True)
            self.last_on_time = now
            
        elif not desired_state and self.relay_state:
            # Want to turn OFF
            if self.last_on_time and (now - self.last_on_time) < self.min_on_s:
                # Haven't been on long enough
                return
            await self._set_relay_state(False)
            self.last_off_time = now
    
    async def _set_relay_state(self, state: bool):
        """Set relay state and update tracking."""
        if state != self.relay_state:
            await self.relay_driver.set_state(state)
            self.relay_state = state
            logger.debug(f"Relay {'ON' if state else 'OFF'}")
    
    async def _log_reading(self):
        """Log current reading to database."""
        try:
            with get_session_sync() as session:
                reading = Reading(
                    smoke_id=self.active_smoke_id,
                    temp_c=self.current_temp_c,
                    temp_f=self.current_temp_f,
                    setpoint_c=self.setpoint_c,
                    setpoint_f=self.setpoint_f,
                    output_bool=self.output_bool,
                    relay_state=self.relay_state,
                    loop_ms=int(self.last_loop_time * 1000) if self.last_loop_time else 0,
                    pid_output=self.pid_output,
                    boost_active=self.boost_active
                )
                session.add(reading)
                session.commit()
                session.refresh(reading)  # Get the ID
                
                # Log all thermocouple readings
                for tc_id, (temp_c, fault) in self.tc_readings.items():
                    if temp_c is not None:
                        temp_f = settings.celsius_to_fahrenheit(temp_c)
                        tc_reading = ThermocoupleReading(
                            reading_id=reading.id,
                            thermocouple_id=tc_id,
                            temp_c=temp_c,
                            temp_f=temp_f,
                            fault=fault
                        )
                        session.add(tc_reading)
                
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log reading: {e}")
    
    async def _log_event(self, kind: str, message: str, meta_json: str = None):
        """Log system event to database."""
        try:
            with get_session_sync() as session:
                event = Event(
                    kind=kind,
                    message=message,
                    meta_json=meta_json
                )
                session.add(event)
                session.commit()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    def get_status(self) -> dict:
        """Get current controller status."""
        # Build thermocouple readings for status
        tc_temps = {}
        for tc_id, (temp_c, fault) in self.tc_readings.items():
            if temp_c is not None:
                tc_temps[tc_id] = {
                    "temp_c": temp_c,
                    "temp_f": settings.celsius_to_fahrenheit(temp_c),
                    "fault": fault
                }
        
        return {
            "running": self.running,
            "boost_active": self.boost_active,
            "boost_until": self.boost_until.isoformat() if self.boost_until else None,
            "control_mode": self.control_mode,
            "active_smoke_id": self.active_smoke_id,
            "current_temp_c": self.current_temp_c,
            "current_temp_f": self.current_temp_f,
            "setpoint_c": self.setpoint_c,
            "setpoint_f": self.setpoint_f,
            "pid_output": self.pid_output,
            "output_bool": self.output_bool,
            "relay_state": self.relay_state,
            "loop_count": self.loop_count,
            "last_loop_time": self.last_loop_time,
            "pid_state": self.pid.get_state(),
            "control_tc_id": self.control_tc_id,
            "thermocouple_readings": tc_temps
        }


# Global controller instance
controller = SmokerController()
