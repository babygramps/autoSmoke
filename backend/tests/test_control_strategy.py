import pytest

from core.control import ThermostatStrategy, TimeProportionalStrategy
from core.pid import PIDController


class DummyAdaptivePID:
    def __init__(self):
        self.samples = []

    def record_sample(self, temp_c, setpoint_c, error):
        self.samples.append((temp_c, setpoint_c, error))

    def evaluate_and_adjust(self, kp, ki, kd):
        return None


class DummyHardwareService:
    def __init__(self):
        self.updated = []

    def update_simulation_setpoint(self, value):
        self.updated.append(value)


class ThermostatController:
    def __init__(self):
        self.output_bool = False
        self.setpoint_c = 100.0
        self.hyst_c = 2.0
        self.pid_output = 0.0
        self.applied = []

    async def apply_relay_with_timing(self, state):
        self.applied.append(state)


class TimeProportionalController:
    def __init__(self):
        self.autotune_active = False
        self.adaptive_pid = DummyAdaptivePID()
        self.pid = PIDController(kp=1.0, ki=0.0, kd=0.0)
        self.setpoint_c = 120.0
        self.time_window_s = 5.0
        self.window_start_time = None
        self.window_on_duration = 0.0
        self.output_bool = False
        self.pid_output = 0.0
        self.hardware_service = DummyHardwareService()
        self.relay_states = []
        self.adaptive_calls = []

    async def set_relay_state(self, state):
        self.relay_states.append(state)

    async def apply_adaptive_pid_adjustment(self, kp, ki, kd, reason):
        self.adaptive_calls.append((kp, ki, kd, reason))


@pytest.mark.asyncio
async def test_thermostat_strategy_toggles_relay():
    controller = ThermostatController()
    strategy = ThermostatStrategy()

    await strategy.execute(controller, 97.0)
    assert controller.output_bool is True
    assert controller.pid_output == 100.0
    assert controller.applied == [True]

    controller.output_bool = True
    await strategy.execute(controller, 103.0)
    assert controller.output_bool is False
    assert controller.applied[-1] is False


@pytest.mark.asyncio
async def test_time_proportional_strategy_updates_state():
    controller = TimeProportionalController()
    strategy = TimeProportionalStrategy()

    await strategy.execute(controller, 90.0)

    assert controller.pid_output >= 0
    assert controller.output_bool is True
    assert controller.relay_states == [True]
    assert controller.hardware_service.updated[-1] == pytest.approx(controller.setpoint_c)
    assert controller.adaptive_calls == []
