import sys
from types import SimpleNamespace

import pytest

from core.session_service import SessionService


class DummySession:
    def __init__(self, active_smoke=None, smoke=None, phase=None):
        self._active_smoke = active_smoke
        self._smoke = smoke
        self._phase = phase

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    # For load_active_smoke
    def exec(self, statement):  # pragma: no cover - compatibility
        class Result:
            def __init__(self, value):
                self._value = value

            def first(self):
                return self._value

        return Result(self._active_smoke)

    # For check_phase_conditions
    def get(self, model, identifier):  # pragma: no cover - compatibility
        if self._smoke is not None and getattr(self._smoke, "id", None) == identifier:
            return self._smoke
        if self._phase is not None and getattr(self._phase, "id", None) == identifier:
            return self._phase
        return self._smoke if self._smoke else self._phase


def test_load_active_smoke_none(monkeypatch):
    monkeypatch.setattr("core.session_service.get_session_sync", lambda: DummySession())

    service = SessionService()
    result = service.load_active_smoke()

    assert result.smoke_id is None
    assert service.active_smoke_id is None


def test_load_active_smoke_with_phase(monkeypatch):
    active_smoke = SimpleNamespace(id=7, name="Brisket", is_active=True)
    phase = SimpleNamespace(target_temp_f=225.0, phase_name="Initial")

    monkeypatch.setattr("core.session_service.get_session_sync", lambda: DummySession(active_smoke=active_smoke))

    from core.session_service import phase_manager

    monkeypatch.setattr(phase_manager, "get_current_phase", lambda smoke_id: phase)

    service = SessionService()
    result = service.load_active_smoke()

    assert result.smoke_id == 7
    assert result.phase_setpoint_f == pytest.approx(225.0)


@pytest.mark.asyncio
async def test_check_phase_conditions_triggers_broadcast(monkeypatch):
    smoke = SimpleNamespace(id=10, current_phase_id=5, pending_phase_transition=False, meat_probe_tc_id=None)
    phase = SimpleNamespace(id=5, is_paused=False)

    session = DummySession(smoke=smoke, phase=phase)
    monkeypatch.setattr("core.session_service.get_session_sync", lambda: session)

    from core.session_service import phase_manager

    monkeypatch.setattr(phase_manager, "check_phase_conditions", lambda *args: (True, "target reached"))
    monkeypatch.setattr(phase_manager, "request_phase_transition", lambda *args: True)
    monkeypatch.setattr(
        phase_manager,
        "get_current_phase",
        lambda smoke_id: SimpleNamespace(id=5, phase_name="Phase1", target_temp_f=250.0),
    )
    monkeypatch.setattr(
        phase_manager,
        "get_next_phase",
        lambda smoke_id: SimpleNamespace(id=6, phase_name="Phase2", target_temp_f=260.0),
    )

    events = []

    class DummyManager:
        async def broadcast_phase_event(self, event, payload):
            events.append((event, payload))

    monkeypatch.setitem(sys.modules, "ws.manager", SimpleNamespace(manager=DummyManager()))

    logged = []

    async def log_event(kind, message):
        logged.append((kind, message))

    service = SessionService()
    service.active_smoke_id = 10

    await service.check_phase_conditions(100.0, {}, log_event)

    assert events
    assert logged == [("phase_transition_ready", "Phase transition ready: target reached")]
