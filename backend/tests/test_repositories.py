"""Tests for database repositories."""

import pytest
from sqlmodel import Session, SQLModel, delete, select

from db.models import Event, Reading, Settings as DBSettings, ThermocoupleReading
from db.repositories import EventsRepository, ReadingsRepository, SettingsRepository
from db.session import engine


@pytest.fixture(autouse=True)
def prepare_database():
    """Ensure database tables exist and clean up after each test."""
    SQLModel.metadata.create_all(engine)
    yield
    with Session(engine) as session:
        session.exec(delete(ThermocoupleReading))
        session.exec(delete(Reading))
        session.exec(delete(Event))
        session.exec(delete(DBSettings))
        session.commit()


def test_settings_repository_crud_roundtrip():
    repo = SettingsRepository()

    # Initially no settings stored
    assert repo.get_settings() is None

    created = repo.get_settings(ensure=True)
    assert created is not None
    assert created.setpoint_f == pytest.approx(225.0)

    updated = repo.update_settings({
        "setpoint_f": 250.0,
        "setpoint_c": 121.11111111111111,
        "adaptive_pid_enabled": False,
    })
    assert updated.setpoint_f == pytest.approx(250.0)
    assert updated.adaptive_pid_enabled is False

    repo.set_adaptive_pid_enabled(True)
    enabled = repo.get_settings()
    assert enabled.adaptive_pid_enabled is True

    reset = repo.reset_settings()
    assert reset.setpoint_f == pytest.approx(225.0)
    assert reset.adaptive_pid_enabled is True


def test_readings_repository_persists_samples():
    repo = ReadingsRepository()

    reading = repo.create_reading(
        reading_data={
            "smoke_id": None,
            "temp_c": 100.0,
            "temp_f": 212.0,
            "setpoint_c": 90.0,
            "setpoint_f": 194.0,
            "output_bool": True,
            "relay_state": True,
            "loop_ms": 500,
            "pid_output": 42.5,
            "boost_active": False,
        },
        thermocouple_samples=[
            {"thermocouple_id": 1, "temp_c": 100.0, "temp_f": 212.0, "fault": False},
            {"thermocouple_id": 2, "temp_c": 90.0, "temp_f": 194.0, "fault": False},
        ],
    )

    with Session(engine) as session:
        stored = session.get(Reading, reading.id)
        assert stored is not None
        samples = session.exec(select(ThermocoupleReading).where(ThermocoupleReading.reading_id == reading.id)).all()
        assert len(samples) == 2
        assert {sample.thermocouple_id for sample in samples} == {1, 2}


def test_events_repository_logs_event():
    repo = EventsRepository()

    event = repo.log_event("unit_test", "Repository created event")

    with Session(engine) as session:
        stored = session.get(Event, event.id)
        assert stored is not None
        assert stored.kind == "unit_test"
        assert stored.message == "Repository created event"
