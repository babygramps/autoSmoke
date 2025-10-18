"""Main smoker controller with PID loop and relay control."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings, ControlMode
from core.hardware import create_temp_sensor, create_relay_driver, SimTempSensor, MultiThermocoupleManager
from core.pid import PIDController
from core.pid_autotune import PIDAutoTuner, TuningRule, AutoTuneState
from core.adaptive_pid import AdaptivePIDController
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
        
        # Load settings from database first (needed to determine sim_mode)
        db_settings = self._load_db_settings()
        
        # Determine simulation mode from database settings (or fall back to config)
        self.sim_mode = db_settings.sim_mode if db_settings else settings.smoker_sim_mode
        logger.info(f"Controller initializing with sim_mode={self.sim_mode} (from {'database' if db_settings else 'config'})")
        
        # Get GPIO settings from database
        gpio_pin = db_settings.gpio_pin if db_settings else settings.smoker_gpio_pin
        relay_active_high = db_settings.relay_active_high if db_settings else settings.smoker_relay_active_high
        
        # Hardware (pass sim_mode explicitly to avoid environment variable issues)
        self.temp_sensor = create_temp_sensor()  # Kept for backward compatibility
        self.relay_driver = self._create_relay_driver(gpio_pin, relay_active_high)
        
        # Multi-thermocouple manager (using database sim_mode setting)
        self.tc_manager = MultiThermocoupleManager(sim_mode=self.sim_mode)
        self.control_tc_id = None  # ID of the control thermocouple
        self.tc_readings = {}  # Latest readings: {tc_id: (temp_c, fault)}
        
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
        
        # Check for hardware fallback immediately after loading (creates alert if needed)
        self._check_hardware_fallback_on_init()
        
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
        self._monitoring_task = None  # Always-on temperature monitoring
        self._loop_interval = 1.0  # 1 Hz
        
        # Statistics
        self.loop_count = 0
        self.last_loop_time = None
        
        # Auto-tuner
        self.autotuner: Optional[PIDAutoTuner] = None
        self.autotune_active = False
        self.autotune_auto_apply = True
        
        # Adaptive PID
        self.adaptive_pid = AdaptivePIDController()
        # Load adaptive PID state from database
        if db_settings and db_settings.adaptive_pid_enabled and self.control_mode == CONTROL_MODE_TIME_PROPORTIONAL:
            self.adaptive_pid.enable()
        elif not db_settings and self.control_mode == CONTROL_MODE_TIME_PROPORTIONAL:
            # Default to enabled if no DB settings
            self.adaptive_pid.enable()
        
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
    
    def _create_relay_driver(self, gpio_pin: int, active_high: bool):
        """Create relay driver based on current sim_mode."""
        if self.sim_mode:
            from core.hardware import SimRelayDriver
            logger.info("Creating simulated relay driver")
            return SimRelayDriver()
        else:
            from core.hardware import RealRelayDriver
            logger.info(f"Creating real relay driver (GPIO pin={gpio_pin}, active_high={active_high})")
            return RealRelayDriver(pin=gpio_pin, active_high=active_high, force_real=True)
    
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
    
    def _check_hardware_fallback_on_init(self):
        """Check for hardware fallback during initialization and create alert if needed."""
        if not self.sim_mode and self.tc_manager.has_fallback_sensors():
            fallback_status = self.tc_manager.get_fallback_status()
            fallback_tcs = []
            
            try:
                with get_session_sync() as session:
                    for tc_id, mode in fallback_status.items():
                        if mode == "simulated":
                            tc = session.get(Thermocouple, tc_id)
                            if tc:
                                fallback_tcs.append(f"{tc.name} (pin {tc.cs_pin})")
                                logger.warning(f"⚠ Thermocouple '{tc.name}' is using FALLBACK SIMULATION - check hardware connection!")
            except Exception as e:
                logger.error(f"Error checking fallback status: {e}")
            
            if fallback_tcs:
                logger.error("=" * 60)
                logger.error("HARDWARE FALLBACK DETECTED!")
                logger.error(f"The following thermocouples are NOT connected:")
                for tc in fallback_tcs:
                    logger.error(f"  - {tc}")
                logger.error("Simulation mode is OFF but hardware is not responding.")
                logger.error("Check your thermocouple connections and CS pins!")
                logger.error("=" * 60)
    
    def reload_thermocouples(self):
        """Reload thermocouple configuration (call after DB changes)."""
        # Clear existing thermocouples
        self.tc_readings = {}
        # Reload from DB
        self._load_thermocouples()
    
    def reload_hardware(self, new_sim_mode: bool, gpio_pin: int = None, relay_active_high: bool = None):
        """
        Reload hardware with new simulation mode setting.
        This recreates the thermocouple manager and relay driver with the new settings.
        WARNING: Only call this when the controller is stopped!
        """
        if self.running:
            logger.error("Cannot reload hardware while controller is running. Stop the controller first.")
            return False
        
        old_sim_mode = self.sim_mode
        self.sim_mode = new_sim_mode
        
        logger.info(f"Reloading hardware: sim_mode changed from {old_sim_mode} to {new_sim_mode}")
        
        # Get current GPIO settings if not provided
        if gpio_pin is None or relay_active_high is None:
            try:
                with get_session_sync() as session:
                    db_settings = session.get(DBSettings, 1)
                    if db_settings:
                        gpio_pin = gpio_pin if gpio_pin is not None else db_settings.gpio_pin
                        relay_active_high = relay_active_high if relay_active_high is not None else db_settings.relay_active_high
                    else:
                        gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                        relay_active_high = relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
            except Exception as e:
                logger.error(f"Failed to load GPIO settings: {e}")
                gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                relay_active_high = relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
        
        # Clean up old relay driver
        if hasattr(self.relay_driver, 'close'):
            logger.info("Closing old relay driver")
            self.relay_driver.close()
        
        # Recreate the relay driver with new sim_mode
        self.relay_driver = self._create_relay_driver(gpio_pin, relay_active_high)
        
        # Recreate the thermocouple manager with new sim_mode
        self.tc_manager = MultiThermocoupleManager(sim_mode=self.sim_mode)
        self.tc_readings = {}
        
        # Reload thermocouple configurations
        self._load_thermocouples()
        
        logger.info(f"Hardware reloaded successfully with sim_mode={self.sim_mode}, GPIO pin={gpio_pin}, active_high={relay_active_high}")
        return True
    
    def update_relay_settings(self, gpio_pin: int = None, relay_active_high: bool = None):
        """
        Update relay GPIO settings without requiring controller restart.
        Can be called when controller is running or stopped.
        """
        from core.hardware import RealRelayDriver
        
        # Get current settings if not provided
        if gpio_pin is None or relay_active_high is None:
            try:
                with get_session_sync() as session:
                    db_settings = session.get(DBSettings, 1)
                    if db_settings:
                        gpio_pin = gpio_pin if gpio_pin is not None else db_settings.gpio_pin
                        relay_active_high = relay_active_high if relay_active_high is not None else db_settings.relay_active_high
                    else:
                        gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                        relay_active_high = relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
            except Exception as e:
                logger.error(f"Failed to load GPIO settings: {e}")
                return False
        
        # If sim mode, just log and return
        if self.sim_mode:
            logger.info(f"Sim mode active, GPIO settings updated in DB but not applied: pin={gpio_pin}, active_high={relay_active_high}")
            return True
        
        # Check if it's a RealRelayDriver that supports reinitialize
        if isinstance(self.relay_driver, RealRelayDriver) and hasattr(self.relay_driver, 'reinitialize'):
            logger.info(f"Updating relay settings: GPIO pin={gpio_pin}, active_high={relay_active_high}")
            self.relay_driver.reinitialize(pin=gpio_pin, active_high=relay_active_high)
            logger.info("✓ Relay settings updated successfully")
            return True
        else:
            logger.warning("Relay driver does not support runtime reconfiguration")
            return False
    
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
                    
                    # Load current phase and apply its setpoint
                    try:
                        from core.phase_manager import phase_manager
                        current_phase = phase_manager.get_current_phase(active_smoke.id)
                        
                        if current_phase:
                            self.set_setpoint(current_phase.target_temp_f)
                            logger.info(f"Applied phase setpoint from loaded session: {current_phase.phase_name} @ {current_phase.target_temp_f}°F")
                    except Exception as e:
                        logger.warning(f"Failed to load phase settings for loaded session: {e}")
                else:
                    logger.info("No active smoke session found")
        except Exception as e:
            logger.warning(f"Failed to load active smoke: {e}")
            self.active_smoke_id = None
    
    def set_active_smoke(self, smoke_id: int):
        """Set the active smoking session and load phase settings."""
        self.active_smoke_id = smoke_id
        logger.info(f"Active smoke session set to ID: {smoke_id}")
        
        # Load current phase and apply its setpoint
        try:
            from core.phase_manager import phase_manager
            current_phase = phase_manager.get_current_phase(smoke_id)
            
            if current_phase:
                # Set controller setpoint to current phase target
                self.set_setpoint(current_phase.target_temp_f)
                logger.info(f"Applied phase setpoint: {current_phase.phase_name} @ {current_phase.target_temp_f}°F")
            else:
                logger.warning(f"No active phase found for smoke {smoke_id}, setpoint not changed")
        except Exception as e:
            logger.error(f"Failed to load phase settings for smoke {smoke_id}: {e}")
    
    def start_monitoring(self):
        """Start the always-on temperature monitoring loop."""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Temperature monitoring started (always-on)")
    
    async def start(self):
        """Start the control loop (active control with relay)."""
        if self.running:
            logger.warning("Controller already running")
            return
        
        # Ensure monitoring is running
        if self._monitoring_task is None:
            self.start_monitoring()
        
        # Reload GPIO settings from database before starting
        try:
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                if db_settings:
                    # Check if GPIO settings in database differ from what's currently configured
                    current_pin = getattr(self.relay_driver, 'pin', None)
                    current_active_high = getattr(self.relay_driver, 'active_high', None)
                    
                    if (current_pin is not None and current_pin != db_settings.gpio_pin) or \
                       (current_active_high is not None and current_active_high != db_settings.relay_active_high):
                        logger.info(f"Detected GPIO settings mismatch, reloading: DB has pin={db_settings.gpio_pin}, active_high={db_settings.relay_active_high}")
                        self.update_relay_settings(db_settings.gpio_pin, db_settings.relay_active_high)
        except Exception as e:
            logger.warning(f"Failed to check GPIO settings on start: {e}")
        
        # If there's an active session, load phase settings before starting
        if self.active_smoke_id:
            try:
                from core.phase_manager import phase_manager
                current_phase = phase_manager.get_current_phase(self.active_smoke_id)
                
                if current_phase:
                    self.set_setpoint(current_phase.target_temp_f)
                    logger.info(f"Starting with phase setpoint: {current_phase.phase_name} @ {current_phase.target_temp_f}°F")
            except Exception as e:
                logger.warning(f"Failed to load phase settings on start: {e}")
        
        self.running = True
        self._control_task = asyncio.create_task(self._control_loop())
        
        # Log startup event
        await self._log_event("controller_start", "Controller started")
        logger.info("Smoker controller started (active control enabled)")
    
    async def stop(self):
        """Stop the control loop (turns off relay, but monitoring continues)."""
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
        logger.info("Smoker controller stopped (active control disabled, monitoring continues)")
    
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
            
            # Enable/disable adaptive PID based on mode and database setting
            if mode == CONTROL_MODE_TIME_PROPORTIONAL:
                # Check if user wants adaptive PID enabled
                try:
                    with get_session_sync() as session:
                        db_settings = session.get(DBSettings, 1)
                        if db_settings and db_settings.adaptive_pid_enabled:
                            self.adaptive_pid.enable()
                            logger.info("Adaptive PID enabled (switched to PID mode)")
                        else:
                            # Default to enabled if no preference
                            self.adaptive_pid.enable()
                            logger.info("Adaptive PID enabled by default (switched to PID mode)")
                except Exception as e:
                    logger.error(f"Failed to load adaptive PID setting: {e}")
                    self.adaptive_pid.enable()  # Default to enabled on error
            else:
                self.adaptive_pid.disable()
                logger.info("Adaptive PID disabled (switched to thermostat mode)")
        
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
    
    async def start_autotune(
        self,
        output_step: float = 50.0,
        lookback_seconds: float = 60.0,
        noise_band: float = 0.5,
        tuning_rule: TuningRule = TuningRule.TYREUS_LUYBEN,
        auto_apply: bool = True
    ) -> bool:
        """
        Start PID auto-tuning process.
        
        Args:
            output_step: Relay step size (% of output, typically 30-60%)
            lookback_seconds: Lookback window for peak detection
            noise_band: Temperature noise band to ignore (degrees C)
            tuning_rule: Which tuning rule to use
            auto_apply: Automatically apply gains when complete (default True)
            
        Returns:
            True if auto-tune started successfully, False otherwise
        """
        if not self.running:
            logger.error("Cannot start auto-tune: controller not running")
            return False
        
        if self.autotune_active:
            logger.warning("Auto-tune already active")
            return False
        
        # Cannot auto-tune during an active smoke session with phases
        if self.active_smoke_id:
            logger.error("Cannot start auto-tune: active smoke session in progress")
            return False
        
        # Cannot auto-tune in thermostat mode (needs PID mode)
        if self.control_mode == CONTROL_MODE_THERMOSTAT:
            logger.error("Cannot start auto-tune: must be in time-proportional (PID) mode")
            return False
        
        # Create auto-tuner instance
        self.autotuner = PIDAutoTuner(
            setpoint=self.setpoint_c,
            output_step=output_step,
            lookback_seconds=lookback_seconds,
            noise_band=noise_band,
            sample_time=self._loop_interval,
            tuning_rule=tuning_rule
        )
        
        # Start the auto-tuning process
        if self.autotuner.start():
            self.autotune_active = True
            self.autotune_auto_apply = auto_apply
            await self._log_event(
                "autotune_start",
                f"Auto-tune started: setpoint={self.setpoint_f:.1f}°F, rule={tuning_rule.value}, auto_apply={auto_apply}"
            )
            logger.info(f"Auto-tune started with rule: {tuning_rule.value}, auto_apply={auto_apply}")
            return True
        else:
            self.autotuner = None
            return False
    
    async def cancel_autotune(self) -> bool:
        """
        Cancel the auto-tuning process.
        
        Returns:
            True if cancelled successfully, False if no auto-tune active
        """
        if not self.autotune_active or not self.autotuner:
            logger.warning("No auto-tune active to cancel")
            return False
        
        self.autotuner.cancel()
        self.autotune_active = False
        
        await self._log_event("autotune_cancel", "Auto-tune cancelled by user")
        logger.info("Auto-tune cancelled")
        
        self.autotuner = None
        return True
    
    async def apply_autotune_gains(self) -> bool:
        """
        Apply the gains calculated by auto-tuner to the PID controller.
        
        Returns:
            True if gains applied successfully, False otherwise
        """
        if not self.autotuner:
            logger.error("No auto-tuner instance available")
            return False
        
        gains = self.autotuner.get_gains()
        if not gains:
            logger.error("Auto-tuner has no valid gains to apply")
            return False
        
        kp, ki, kd = gains
        
        # Apply gains to PID controller
        await self.set_pid_gains(kp, ki, kd)
        
        # Save to database
        try:
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                if db_settings:
                    db_settings.kp = kp
                    db_settings.ki = ki
                    db_settings.kd = kd
                    session.add(db_settings)
                    session.commit()
                    logger.info(f"Auto-tuned gains saved to database: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}")
                else:
                    logger.error("No database settings found to save gains")
                    return False
        except Exception as e:
            logger.error(f"Failed to save auto-tuned gains to database: {e}")
            return False
        
        await self._log_event(
            "autotune_apply",
            f"Auto-tuned PID gains applied: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}"
        )
        
        # Clear auto-tuner and resume normal operation
        self.autotune_active = False
        self.autotuner = None
        self.autotune_auto_apply = True
        
        return True
    
    def get_autotune_status(self) -> Optional[dict]:
        """
        Get current auto-tune status.
        
        Returns:
            Status dict if auto-tune active, None otherwise
        """
        if not self.autotuner:
            return None
        
        return self.autotuner.get_status()
    
    def enable_adaptive_pid(self):
        """Enable continuous adaptive PID tuning."""
        logger.info(f"🎛️ enable_adaptive_pid() called - Current mode: {self.control_mode}, Running: {self.running}")
        
        if self.control_mode != CONTROL_MODE_TIME_PROPORTIONAL:
            logger.warning(f"❌ Cannot enable adaptive PID: not in time-proportional mode (current: {self.control_mode})")
            return False
        
        logger.info("✅ Enabling adaptive PID controller...")
        self.adaptive_pid.enable()
        
        # Save to database
        try:
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                if db_settings:
                    logger.info(f"💾 Saving adaptive_pid_enabled=True to database (was: {db_settings.adaptive_pid_enabled})")
                    db_settings.adaptive_pid_enabled = True
                    session.add(db_settings)
                    session.commit()
                    logger.info("✅ Database updated successfully")
                else:
                    logger.error("❌ No database settings found!")
        except Exception as e:
            logger.error(f"❌ Failed to save adaptive PID enabled state: {e}")
        
        logger.info(f"✅ Adaptive PID tuning enabled by user - Status: {self.adaptive_pid.get_status()}")
        return True
    
    def disable_adaptive_pid(self):
        """Disable continuous adaptive PID tuning."""
        logger.info(f"🎛️ disable_adaptive_pid() called")
        
        self.adaptive_pid.disable()
        
        # Save to database
        try:
            with get_session_sync() as session:
                db_settings = session.get(DBSettings, 1)
                if db_settings:
                    logger.info(f"💾 Saving adaptive_pid_enabled=False to database (was: {db_settings.adaptive_pid_enabled})")
                    db_settings.adaptive_pid_enabled = False
                    session.add(db_settings)
                    session.commit()
                    logger.info("✅ Database updated successfully")
                else:
                    logger.error("❌ No database settings found!")
        except Exception as e:
            logger.error(f"❌ Failed to save adaptive PID disabled state: {e}")
        
        logger.info(f"✅ Adaptive PID tuning disabled by user - Status: {self.adaptive_pid.get_status()}")
        return True
    
    def get_adaptive_pid_status(self) -> dict:
        """Get adaptive PID status."""
        return self.adaptive_pid.get_status()
    
    async def _monitoring_loop(self):
        """Always-on temperature monitoring loop (runs even when controller is stopped)."""
        logger.info("Temperature monitoring loop started")
        while True:  # Runs forever
            try:
                # Read temperatures from all thermocouples
                self.tc_readings = await self.tc_manager.read_all()
                
                # Get control thermocouple temperature
                control_temp_c = None
                control_fault = True
                
                if self.control_tc_id and self.control_tc_id in self.tc_readings:
                    control_temp_c, control_fault = self.tc_readings[self.control_tc_id]
                
                # Update temperature values for status display
                if control_temp_c is not None and not control_fault:
                    self.current_temp_c = control_temp_c
                    self.current_temp_f = settings.celsius_to_fahrenheit(control_temp_c)
                else:
                    # Keep last known values but could mark as stale
                    pass
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Sleep for 1 second
            await asyncio.sleep(1.0)
    
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
        # Note: Temperature readings are handled by monitoring loop
        # Just use the latest readings
        
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
            
            # Cancel auto-tune if active (sensor fault is critical)
            if self.autotune_active:
                logger.error("Sensor fault detected, cancelling auto-tune")
                await self.cancel_autotune()
            
            await self._log_event("sensor_fault", f"Control thermocouple reading failed (ID={self.control_tc_id})")
            logger.error(f"Control thermocouple reading failed (ID={self.control_tc_id})")
            return
        
        temp_c = control_temp_c
        
        # Check if boost mode should end
        if self.boost_active and self.boost_until and datetime.utcnow() >= self.boost_until:
            await self.disable_boost()
        
        # Determine relay state
        if self.autotune_active and self.autotuner:
            # Auto-tune mode - use auto-tuner output
            await self._autotune_control(temp_c)
        elif self.boost_active:
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
        
        # Check phase conditions (if session has phases)
        if self.active_smoke_id:
            await self._check_phase_conditions(temp_c)
        
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
        # Record sample for adaptive PID (only if not auto-tuning)
        if not self.autotune_active:
            error = self.setpoint_c - temp_c
            self.adaptive_pid.record_sample(temp_c, self.setpoint_c, error)
            
            # Check if adaptive PID suggests an adjustment
            adjustment = self.adaptive_pid.evaluate_and_adjust(
                self.pid.kp,
                self.pid.ki,
                self.pid.kd
            )
            
            if adjustment:
                new_kp, new_ki, new_kd, reason = adjustment
                # Apply the adaptive adjustment
                await self.set_pid_gains(new_kp, new_ki, new_kd)
                
                # Save to database
                try:
                    with get_session_sync() as session:
                        db_settings = session.get(DBSettings, 1)
                        if db_settings:
                            db_settings.kp = new_kp
                            db_settings.ki = new_ki
                            db_settings.kd = new_kd
                            session.add(db_settings)
                            session.commit()
                except Exception as e:
                    logger.error(f"Failed to save adaptive PID gains: {e}")
                
                await self._log_event(
                    "adaptive_pid_adjustment",
                    f"Adaptive PID: {reason} | Kp={new_kp:.4f}, Ki={new_ki:.4f}, Kd={new_kd:.4f}"
                )
        
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
    
    async def _autotune_control(self, temp_c: float):
        """
        Auto-tune control mode - use auto-tuner to determine relay state.
        
        The auto-tuner uses relay feedback to induce oscillations and
        measure system characteristics for PID gain calculation.
        """
        if not self.autotuner:
            logger.error("Auto-tune control called but no auto-tuner instance")
            self.autotune_active = False
            return
        
        # Update auto-tuner with current temperature
        output, is_complete = self.autotuner.update(temp_c)
        
        # Convert output percentage to boolean for relay
        # output > 0 means relay should be ON
        self.output_bool = output > 0
        self.pid_output = output  # For logging
        
        # Apply relay state
        await self._set_relay_state(self.output_bool)
        
        # Check if auto-tune completed
        if is_complete:
            status = self.autotuner.get_status()
            state = status.get("state", "unknown")
            
            if state == AutoTuneState.SUCCEEDED.value:
                gains = self.autotuner.get_gains()
                if gains:
                    kp, ki, kd = gains
                    logger.info(f"🎉 Auto-tune COMPLETED successfully!")
                    logger.info(f"   Calculated gains: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}")
                    logger.info(f"   System characteristics: Ku={self.autotuner.ku:.4f}, Pu={self.autotuner.pu:.2f}s")
                    
                    await self._log_event(
                        "autotune_complete",
                        f"Auto-tune completed: Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}"
                    )
                    
                    # Auto-apply gains if enabled
                    if self.autotune_auto_apply:
                        logger.info("   Auto-applying gains...")
                        await self.apply_autotune_gains()
                        logger.info("   ✅ Gains applied successfully! Controller resuming with new PID values.")
                    else:
                        logger.info("   Gains ready. Use apply_autotune_gains() to apply these values")
            else:
                logger.warning(f"Auto-tune completed with state: {state}")
                await self._log_event(
                    "autotune_failed",
                    f"Auto-tune failed or cancelled: {state}"
                )
                self.autotune_active = False
                self.autotuner = None
    
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
    
    async def _check_phase_conditions(self, temp_c: float):
        """Check if current phase conditions are met and request transition if needed."""
        try:
            from core.phase_manager import phase_manager
            from db.models import Smoke, SmokePhase
            
            # Get smoke session
            with get_session_sync() as session:
                smoke = session.get(Smoke, self.active_smoke_id)
                if not smoke or not smoke.current_phase_id:
                    return  # No active phase
                
                # Don't check if already pending transition
                if smoke.pending_phase_transition:
                    return
                
                # Get current phase to check if it's paused
                current_phase = session.get(SmokePhase, smoke.current_phase_id)
                if not current_phase:
                    return
                
                # Don't check conditions if phase is paused
                if current_phase.is_paused:
                    return
                
                meat_probe_tc_id = smoke.meat_probe_tc_id
            
            # Get meat temperature if meat probe is configured
            meat_temp_f = None
            if meat_probe_tc_id and meat_probe_tc_id in self.tc_readings:
                meat_temp_c, fault = self.tc_readings[meat_probe_tc_id]
                if not fault and meat_temp_c is not None:
                    meat_temp_f = settings.celsius_to_fahrenheit(meat_temp_c)
            
            # Check if phase conditions are met
            current_temp_f = settings.celsius_to_fahrenheit(temp_c)
            conditions_met, reason = phase_manager.check_phase_conditions(
                self.active_smoke_id,
                current_temp_f,
                meat_temp_f
            )
            
            if conditions_met:
                # Request phase transition
                success = phase_manager.request_phase_transition(self.active_smoke_id, reason)
                if success:
                    logger.info(f"Phase transition requested for smoke {self.active_smoke_id}: {reason}")
                    
                    # Emit websocket event
                    try:
                        from ws.manager import manager as ws_manager
                        current_phase = phase_manager.get_current_phase(self.active_smoke_id)
                        next_phase = phase_manager.get_next_phase(self.active_smoke_id)
                        
                        await ws_manager.broadcast_phase_event("phase_transition_ready", {
                            "smoke_id": self.active_smoke_id,
                            "reason": reason,
                            "current_phase": {
                                "id": current_phase.id,
                                "phase_name": current_phase.phase_name,
                                "target_temp_f": current_phase.target_temp_f
                            } if current_phase else None,
                            "next_phase": {
                                "id": next_phase.id,
                                "phase_name": next_phase.phase_name,
                                "target_temp_f": next_phase.target_temp_f
                            } if next_phase else None
                        })
                    except Exception as e:
                        logger.error(f"Failed to broadcast phase transition event: {e}")
                    
                    await self._log_event(
                        "phase_transition_ready",
                        f"Phase transition ready: {reason}"
                    )
        
        except Exception as e:
            logger.error(f"Failed to check phase conditions: {e}")
    
    def get_current_phase_info(self) -> Optional[dict]:
        """Get current phase information for status."""
        try:
            from core.phase_manager import phase_manager
            
            if not self.active_smoke_id:
                return None
            
            current_phase = phase_manager.get_current_phase(self.active_smoke_id)
            if not current_phase:
                return None
            
            import json
            return {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "phase_order": current_phase.phase_order,
                "target_temp_f": current_phase.target_temp_f,
                "started_at": current_phase.started_at.isoformat() if current_phase.started_at else None,
                "is_active": current_phase.is_active,
                "completion_conditions": json.loads(current_phase.completion_conditions)
            }
        except Exception as e:
            logger.error(f"Failed to get current phase info: {e}")
            return None
    
    def get_status(self) -> dict:
        """Get current controller status."""
        # Build thermocouple readings for status
        tc_temps = {}
        tc_status = self.tc_manager.get_fallback_status()
        for tc_id, (temp_c, fault) in self.tc_readings.items():
            if temp_c is not None:
                tc_temps[tc_id] = {
                    "temp_c": temp_c,
                    "temp_f": settings.celsius_to_fahrenheit(temp_c),
                    "fault": fault,
                    "mode": tc_status.get(tc_id, "unknown")  # 'real' or 'simulated'
                }
        
        # Get phase information if active session
        current_phase = self.get_current_phase_info()
        pending_phase_transition = False
        
        if self.active_smoke_id:
            try:
                with get_session_sync() as session:
                    from db.models import Smoke
                    smoke = session.get(Smoke, self.active_smoke_id)
                    if smoke:
                        pending_phase_transition = smoke.pending_phase_transition
            except Exception as e:
                logger.error(f"Failed to get smoke status: {e}")
        
        # Check if using fallback simulation
        using_fallback = self.tc_manager.has_fallback_sensors()
        
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
            "thermocouple_readings": tc_temps,
            "current_phase": current_phase,
            "pending_phase_transition": pending_phase_transition,
            "sim_mode": self.sim_mode,
            "using_fallback_simulation": using_fallback,
            "autotune_active": self.autotune_active,
            "autotune_status": self.get_autotune_status(),
            "adaptive_pid": self.get_adaptive_pid_status()
        }


# Global controller instance
controller = SmokerController()
