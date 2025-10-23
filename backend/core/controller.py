"""Main smoker controller with PID loop and relay control."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings
from core.control import ThermostatStrategy, TimeProportionalStrategy
from core.hardware import SimTempSensor
from core.hardware_service import HardwareService
from core.session_service import SessionService
from core.pid import PIDController
from core.pid_autotune import PIDAutoTuner, TuningRule, AutoTuneState
from core.adaptive_pid import AdaptivePIDController
from core.alerts import AlertManager
from db.models import Smoke, CONTROL_MODE_THERMOSTAT, CONTROL_MODE_TIME_PROPORTIONAL
from db.repositories import EventsRepository, ReadingsRepository, SettingsRepository
from db.session import get_session_sync

logger = logging.getLogger(__name__)


class SmokerController:
    """Main smoker controller managing PID loop and relay control."""
    
    def __init__(
        self,
        settings_repository: SettingsRepository | None = None,
        readings_repository: ReadingsRepository | None = None,
        events_repository: EventsRepository | None = None,
        alert_manager: AlertManager | None = None,
    ):
        self.settings_repo = settings_repository or SettingsRepository()
        self.readings_repo = readings_repository or ReadingsRepository()
        self.events_repo = events_repository or EventsRepository()
        self.alert_manager = alert_manager or AlertManager()

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
        
        # Control state
        if db_settings:
            self.setpoint_c = db_settings.setpoint_c
            self.setpoint_f = db_settings.setpoint_f
        else:
            self.setpoint_c = settings.get_setpoint_celsius()
            self.setpoint_f = settings.get_setpoint_fahrenheit()

        # Hardware orchestration
        self.hardware_service = HardwareService(
            sim_mode=self.sim_mode,
            gpio_pin=gpio_pin,
            relay_active_high=relay_active_high,
            setpoint_c=self.setpoint_c,
        )
        self._sync_hardware_state()
        self.hardware_service.load_thermocouples(self.setpoint_c)
        self._sync_hardware_state()
        self.hardware_service.check_hardware_fallback()

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
        self.session_service = SessionService()
        session_load = self.session_service.load_active_smoke()
        self.active_smoke_id = session_load.smoke_id
        if session_load.phase_setpoint_f is not None:
            self._apply_loaded_setpoint(session_load.phase_setpoint_f)
        
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

        self.control_strategies = {
            CONTROL_MODE_THERMOSTAT: ThermostatStrategy(),
            CONTROL_MODE_TIME_PROPORTIONAL: TimeProportionalStrategy(),
        }

        logger.info("SmokerController initialized")
    
    def _load_db_settings(self):
        """Load settings from database, or return None if not found."""
        try:
            db_settings = self.settings_repo.get_settings()
            if db_settings:
                logger.info("Loaded settings from database")
                return db_settings
            logger.info("No database settings found, using config defaults")
            return None
        except Exception as e:
            logger.warning(f"Failed to load database settings: {e}. Using config defaults.")
            return None
    
    def _sync_hardware_state(self) -> None:
        self.temp_sensor = self.hardware_service.temp_sensor
        self.relay_driver = self.hardware_service.relay_driver
        self.tc_manager = self.hardware_service.tc_manager
        self.tc_readings = self.hardware_service.tc_readings
        self.control_tc_id = self.hardware_service.control_tc_id

    def _apply_loaded_setpoint(self, setpoint_f: float) -> None:
        self.setpoint_f = setpoint_f
        self.setpoint_c = settings.fahrenheit_to_celsius(setpoint_f)
        self.hardware_service.update_simulation_setpoint(self.setpoint_c)
    
    def reload_thermocouples(self):
        """Reload thermocouple configuration (call after DB changes)."""
        self.hardware_service.load_thermocouples(self.setpoint_c)
        self._sync_hardware_state()

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
                db_settings = self.settings_repo.get_settings()
                if db_settings:
                    gpio_pin = gpio_pin if gpio_pin is not None else db_settings.gpio_pin
                    relay_active_high = (
                        relay_active_high if relay_active_high is not None else db_settings.relay_active_high
                    )
                else:
                    gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                    relay_active_high = (
                        relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
                    )
            except Exception as e:
                logger.error(f"Failed to load GPIO settings: {e}")
                gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                relay_active_high = relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
        
        reloaded = self.hardware_service.reload_hardware(
            new_sim_mode=new_sim_mode,
            setpoint_c=self.setpoint_c,
            gpio_pin=gpio_pin,
            relay_active_high=relay_active_high,
        )
        self._sync_hardware_state()
        logger.info(
            "Hardware reloaded successfully with sim_mode=%s, GPIO pin=%s, active_high=%s",
            self.sim_mode,
            gpio_pin,
            relay_active_high,
        )
        return reloaded

    def update_relay_settings(self, gpio_pin: int = None, relay_active_high: bool = None):
        """
        Update relay GPIO settings without requiring controller restart.
        Can be called when controller is running or stopped.
        """
        # Get current settings if not provided
        if gpio_pin is None or relay_active_high is None:
            try:
                db_settings = self.settings_repo.get_settings()
                if db_settings:
                    gpio_pin = gpio_pin if gpio_pin is not None else db_settings.gpio_pin
                    relay_active_high = (
                        relay_active_high if relay_active_high is not None else db_settings.relay_active_high
                    )
                else:
                    gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                    relay_active_high = (
                        relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
                    )
            except Exception as e:
                logger.error(f"Failed to load GPIO settings: {e}")
                return False
        
        # If sim mode, just log and return
        if self.sim_mode:
            logger.info(f"Sim mode active, GPIO settings updated in DB but not applied: pin={gpio_pin}, active_high={relay_active_high}")
            return True

        updated = self.hardware_service.update_relay_settings(gpio_pin, relay_active_high)
        self._sync_hardware_state()
        if updated:
            logger.info("✓ Relay settings updated successfully")
        return updated
    
    def set_active_smoke(self, smoke_id: int):
        """Set the active smoking session and load phase settings."""
        result = self.session_service.set_active_smoke(smoke_id)
        self.active_smoke_id = result.smoke_id

        if result.phase_setpoint_f is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.set_setpoint(result.phase_setpoint_f))
            except RuntimeError:
                self._apply_loaded_setpoint(result.phase_setpoint_f)
    
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
            db_settings = self.settings_repo.get_settings()
            if db_settings:
                # Check if GPIO settings in database differ from what's currently configured
                current_pin = getattr(self.relay_driver, 'pin', None)
                current_active_high = getattr(self.relay_driver, 'active_high', None)

                if (current_pin is not None and current_pin != db_settings.gpio_pin) or (
                    current_active_high is not None and current_active_high != db_settings.relay_active_high
                ):
                    logger.info(
                        "Detected GPIO settings mismatch, reloading: DB has pin=%s, active_high=%s",
                        db_settings.gpio_pin,
                        db_settings.relay_active_high,
                    )
                    self.update_relay_settings(db_settings.gpio_pin, db_settings.relay_active_high)
        except Exception as e:
            logger.warning(f"Failed to check GPIO settings on start: {e}")
        
        # If there's an active session, load phase settings before starting
        if self.active_smoke_id:
            phase_info = self.session_service.get_current_phase_info()
            if phase_info and phase_info.get("target_temp_f") is not None:
                await self.set_setpoint(phase_info["target_temp_f"])
                logger.info(
                    "Starting with phase setpoint: %s @ %s°F",
                    phase_info.get("phase_name"),
                    phase_info.get("target_temp_f"),
                )
        
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

    def _pid_to_boolean(self, temp_c: float) -> bool:
        if self.output_bool:
            return temp_c < (self.setpoint_c + self.hyst_c)
        return temp_c < (self.setpoint_c - self.hyst_c)

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
                    db_settings = self.settings_repo.get_settings()
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

    async def apply_adaptive_pid_adjustment(self, kp: float, ki: float, kd: float, reason: str) -> None:
        await self.set_pid_gains(kp, ki, kd)

        try:
            self.settings_repo.set_pid_gains(kp, ki, kd)
        except Exception as exc:
            logger.error(f"Failed to save adaptive PID gains: {exc}")

        await self._log_event(
            "adaptive_pid_adjustment",
            f"Adaptive PID: {reason} | Kp={kp:.4f}, Ki={ki:.4f}, Kd={kd:.4f}",
        )
    
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
            self.settings_repo.set_pid_gains(kp, ki, kd)
            logger.info(
                "Auto-tuned gains saved to database: Kp=%s, Ki=%s, Kd=%s",
                f"{kp:.4f}",
                f"{ki:.4f}",
                f"{kd:.4f}",
            )
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
            current = self.settings_repo.get_settings(ensure=True)
            previous = current.adaptive_pid_enabled if current else None
            self.settings_repo.set_adaptive_pid_enabled(True)
            logger.info(
                "💾 Saving adaptive_pid_enabled=True to database (was: %s)",
                previous,
            )
            logger.info("✅ Database updated successfully")
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
            current = self.settings_repo.get_settings(ensure=True)
            previous = current.adaptive_pid_enabled if current else None
            self.settings_repo.set_adaptive_pid_enabled(False)
            logger.info(
                "💾 Saving adaptive_pid_enabled=False to database (was: %s)",
                previous,
            )
            logger.info("✅ Database updated successfully")
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
                self.tc_readings = await self.hardware_service.read_thermocouples()
                self.control_tc_id = self.hardware_service.control_tc_id

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
                
                # Log reading to database (always log, even when controller is stopped)
                await self._log_reading()
                
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
            strategy = self.control_strategies.get(self.control_mode)
            if strategy:
                await strategy.execute(self, temp_c)
            else:
                logger.error("No control strategy found for mode: %s", self.control_mode)

        # Check phase conditions (if session has phases)
        if self.active_smoke_id:
            await self.session_service.check_phase_conditions(temp_c, self.tc_readings, self._log_event)
        
        # Note: Readings are logged by monitoring loop, not here
        # This prevents duplicate logging when controller is running
        
        # Check alerts
        await self.alert_manager.check_alerts(self.get_status())
    
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

    async def apply_relay_with_timing(self, desired_state: bool) -> None:
        await self._apply_relay_with_timing(desired_state)

    async def set_relay_state(self, state: bool) -> None:
        await self._set_relay_state(state)
    
    async def _log_reading(self):
        """Log current reading to database."""
        try:
            reading_data = {
                "smoke_id": self.active_smoke_id,
                "temp_c": self.current_temp_c,
                "temp_f": self.current_temp_f,
                "setpoint_c": self.setpoint_c,
                "setpoint_f": self.setpoint_f,
                "output_bool": self.output_bool,
                "relay_state": self.relay_state,
                "loop_ms": int(self.last_loop_time * 1000) if self.last_loop_time else 0,
                "pid_output": self.pid_output,
                "boost_active": self.boost_active,
            }

            tc_samples = []
            for tc_id, (temp_c, fault) in self.tc_readings.items():
                if temp_c is None:
                    continue
                tc_samples.append({
                    "thermocouple_id": tc_id,
                    "temp_c": temp_c,
                    "temp_f": settings.celsius_to_fahrenheit(temp_c),
                    "fault": fault,
                })

            await self.readings_repo.create_reading_async(reading_data, tc_samples)
        except Exception as e:
            logger.error(f"Failed to log reading: {e}")

    async def _log_event(self, kind: str, message: str, meta_json: str = None):
        """Log system event to database."""
        try:
            await self.events_repo.log_event_async(kind, message, meta_json)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    def get_current_phase_info(self) -> Optional[dict]:
        return self.session_service.get_current_phase_info()
    
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

