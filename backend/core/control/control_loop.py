"""Control loop strategies for smoker controller."""

from __future__ import annotations

import time
from abc import ABC
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - circular import safe typing
    from core.controller import SmokerController


class ControlLoopStrategy(Protocol):
    """Protocol for control loop strategies."""

    async def execute(self, controller: "SmokerController", temp_c: float) -> None:
        """Execute control logic for the current temperature reading."""


class _BaseStrategy(ABC):
    """Base implementation shared between strategies."""

    async def execute(self, controller: "SmokerController", temp_c: float) -> None:  # pragma: no cover - abstract
        raise NotImplementedError


class ThermostatStrategy(_BaseStrategy):
    """Simple on/off thermostat control with hysteresis."""

    async def execute(self, controller: "SmokerController", temp_c: float) -> None:
        if controller.output_bool:
            controller.output_bool = temp_c < (controller.setpoint_c + controller.hyst_c)
        else:
            controller.output_bool = temp_c < (controller.setpoint_c - controller.hyst_c)

        controller.pid_output = 100.0 if controller.output_bool else 0.0
        await controller.apply_relay_with_timing(controller.output_bool)


class TimeProportionalStrategy(_BaseStrategy):
    """PID driven duty cycle control strategy."""

    async def execute(self, controller: "SmokerController", temp_c: float) -> None:
        if not controller.autotune_active:
            error = controller.setpoint_c - temp_c
            controller.adaptive_pid.record_sample(temp_c, controller.setpoint_c, error)

            adjustment = controller.adaptive_pid.evaluate_and_adjust(
                controller.pid.kp,
                controller.pid.ki,
                controller.pid.kd,
            )

            if adjustment:
                new_kp, new_ki, new_kd, reason = adjustment
                await controller.apply_adaptive_pid_adjustment(new_kp, new_ki, new_kd, reason)

        controller.pid_output = controller.pid.compute(controller.setpoint_c, temp_c)

        now = time.time()
        if controller.window_start_time is None:
            controller.window_start_time = now
            controller.window_on_duration = (controller.pid_output / 100.0) * controller.time_window_s

        elapsed = now - controller.window_start_time
        if elapsed >= controller.time_window_s:
            controller.window_start_time = now
            controller.window_on_duration = (controller.pid_output / 100.0) * controller.time_window_s
            elapsed = 0

        controller.output_bool = elapsed < controller.window_on_duration

        await controller.set_relay_state(controller.output_bool)

        # Update simulation sensors with current setpoint for consistency
        controller.hardware_service.update_simulation_setpoint(controller.setpoint_c)
