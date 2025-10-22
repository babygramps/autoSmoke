from types import SimpleNamespace

from core.hardware_service import HardwareService


class DummySession:
    def __init__(self, thermocouples):
        self._thermocouples = thermocouples

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def exec(self, statement):  # pragma: no cover - signature compatibility
        class Result:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        return Result(self._thermocouples)


def test_load_thermocouples_sets_control_id(monkeypatch):
    thermocouples = [
        SimpleNamespace(id=1, cs_pin=5, name="Pit", is_control=False, enabled=True, order=1),
        SimpleNamespace(id=2, cs_pin=6, name="Food", is_control=True, enabled=True, order=2),
    ]

    monkeypatch.setattr("core.hardware_service.get_session_sync", lambda: DummySession(thermocouples))

    service = HardwareService(sim_mode=True, gpio_pin=17, relay_active_high=False, setpoint_c=100.0)
    service.load_thermocouples(100.0)

    assert service.control_tc_id == 2
    assert len(service.tc_manager.sim_temps) == 2


def test_update_relay_settings_sim_mode(monkeypatch):
    service = HardwareService(sim_mode=True, gpio_pin=17, relay_active_high=False, setpoint_c=90.0)

    assert service.update_relay_settings(23, True)


def test_reload_hardware_reinitializes(monkeypatch):
    service = HardwareService(sim_mode=True, gpio_pin=17, relay_active_high=False, setpoint_c=80.0)

    result = service.reload_hardware(
        new_sim_mode=True,
        setpoint_c=85.0,
        gpio_pin=22,
        relay_active_high=True,
    )

    assert result is True
    assert service.sim_mode is True
    assert service.control_tc_id is None
