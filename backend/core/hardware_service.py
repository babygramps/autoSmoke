"""Service encapsulating smoker hardware orchestration."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from core.config import settings
from core.hardware import (
    MultiThermocoupleManager,
    RealRelayDriver,
    RealTempSensor,
    RelayDriver,
    SimRelayDriver,
    SimTempSensor,
    TempSensor,
)
from db.models import Settings as DBSettings, Thermocouple
from db.session import get_session_sync

logger = logging.getLogger(__name__)


class HardwareService:
    """Manage GPIO relay and thermocouple hardware lifecycle."""

    def __init__(self, sim_mode: bool, gpio_pin: int, relay_active_high: bool, setpoint_c: float) -> None:
        self.sim_mode = sim_mode
        self.relay_driver: RelayDriver = self._create_relay_driver(gpio_pin, relay_active_high)
        self.temp_sensor: TempSensor = self._create_temp_sensor()
        self.tc_manager = MultiThermocoupleManager(sim_mode=sim_mode)
        self.tc_readings: Dict[int, Tuple[Optional[float], bool]] = {}
        self.control_tc_id: Optional[int] = None
        self.update_simulation_setpoint(setpoint_c)

    def _create_temp_sensor(self) -> TempSensor:
        if self.sim_mode:
            logger.info("Creating simulated temperature sensor")
            return SimTempSensor()
        logger.info("Creating real temperature sensor")
        return RealTempSensor()

    def _create_relay_driver(self, gpio_pin: int, active_high: bool) -> RelayDriver:
        if self.sim_mode:
            logger.info("Creating simulated relay driver")
            return SimRelayDriver()
        logger.info("Creating real relay driver")
        return RealRelayDriver(pin=gpio_pin, active_high=active_high, force_real=True)

    def load_thermocouples(self, setpoint_c: float) -> None:
        """Load thermocouples from database into the manager."""
        try:
            with get_session_sync() as session:
                from sqlmodel import select

                statement = select(Thermocouple).where(Thermocouple.enabled == True).order_by(Thermocouple.order)
                thermocouples = session.exec(statement).all()

                if not thermocouples:
                    logger.warning("No thermocouples configured in database")
                    return

                self.tc_manager = MultiThermocoupleManager(sim_mode=self.sim_mode)
                self.tc_readings.clear()
                self.control_tc_id = None

                for tc in thermocouples:
                    self.tc_manager.add_thermocouple(tc.id, tc.cs_pin, tc.name)
                    if tc.is_control:
                        self.control_tc_id = tc.id

                if self.control_tc_id is None and thermocouples:
                    self.control_tc_id = thermocouples[0].id
                    logger.warning("No control thermocouple specified, using first configured sensor")

                logger.info("Loaded %d thermocouples", len(thermocouples))
                self.update_simulation_setpoint(setpoint_c)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to load thermocouples: %s", exc)

    def update_simulation_setpoint(self, setpoint_c: float) -> None:
        if isinstance(self.temp_sensor, SimTempSensor):
            self.temp_sensor.set_setpoint(setpoint_c)
        self.tc_manager.update_setpoint(setpoint_c)

    def check_hardware_fallback(self) -> None:
        if self.sim_mode or not self.tc_manager.has_fallback_sensors():
            return

        fallback_status = self.tc_manager.get_fallback_status()
        fallback_tcs = []

        try:
            with get_session_sync() as session:
                for tc_id, mode in fallback_status.items():
                    if mode == "simulated":
                        tc = session.get(Thermocouple, tc_id)
                        if tc:
                            fallback_tcs.append(f"{tc.name} (pin {tc.cs_pin})")
                            logger.warning(
                                "Thermocouple '%s' is using fallback simulation - check hardware!", tc.name
                            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error checking fallback status: %s", exc)
            return

        if fallback_tcs:
            logger.error("=" * 60)
            logger.error("HARDWARE FALLBACK DETECTED!")
            logger.error("The following thermocouples are NOT connected:")
            for tc in fallback_tcs:
                logger.error("  - %s", tc)
            logger.error("Simulation mode is OFF but hardware is not responding.")
            logger.error("Check thermocouple connections and CS pins!")
            logger.error("=" * 60)

    async def read_thermocouples(self) -> Dict[int, Tuple[Optional[float], bool]]:
        self.tc_readings = await self.tc_manager.read_all()
        return self.tc_readings

    def reload_hardware(
        self,
        new_sim_mode: bool,
        setpoint_c: float,
        gpio_pin: Optional[int] = None,
        relay_active_high: Optional[bool] = None,
    ) -> bool:
        if gpio_pin is None or relay_active_high is None:
            try:
                with get_session_sync() as session:
                    db_settings = session.get(DBSettings, 1)
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
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to load GPIO settings: %s", exc)
                gpio_pin = gpio_pin if gpio_pin is not None else settings.smoker_gpio_pin
                relay_active_high = (
                    relay_active_high if relay_active_high is not None else settings.smoker_relay_active_high
                )

        assert gpio_pin is not None and relay_active_high is not None

        if hasattr(self.relay_driver, "close"):
            try:
                self.relay_driver.close()  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to close relay driver: %s", exc)

        self.sim_mode = new_sim_mode
        self.relay_driver = self._create_relay_driver(gpio_pin, relay_active_high)
        self.temp_sensor = self._create_temp_sensor()
        self.tc_manager = MultiThermocoupleManager(sim_mode=new_sim_mode)
        self.tc_readings = {}
        self.control_tc_id = None
        self.update_simulation_setpoint(setpoint_c)
        self.load_thermocouples(setpoint_c)
        return True

    def update_relay_settings(self, gpio_pin: int, relay_active_high: bool) -> bool:
        if self.sim_mode:
            logger.info(
                "Sim mode active, GPIO settings updated in DB but not applied: pin=%s, active_high=%s",
                gpio_pin,
                relay_active_high,
            )
            return True

        if isinstance(self.relay_driver, RealRelayDriver) and hasattr(self.relay_driver, "reinitialize"):
            self.relay_driver.reinitialize(pin=gpio_pin, active_high=relay_active_high)
            return True

        logger.warning("Relay driver does not support runtime reconfiguration")
        return False
