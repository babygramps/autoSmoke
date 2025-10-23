"""Repository for persisting smoker readings."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Iterable

from sqlmodel import Session

from db.models import Reading, ThermocoupleReading
from db.session import get_session_sync

SessionFactory = Callable[[], Session]


class ReadingsRepository:
    """Encapsulates storage of readings and thermocouple samples."""

    def __init__(self, session_factory: SessionFactory = get_session_sync) -> None:
        self._session_factory = session_factory

    def _create_session(self) -> Session:
        session = self._session_factory()
        if isinstance(session, Session):
            return session
        return session  # type: ignore[return-value]

    def create_reading(
        self,
        reading_data: Dict[str, Any],
        thermocouple_samples: Iterable[Dict[str, Any]],
    ) -> Reading:
        session = self._create_session()
        try:
            reading = Reading(**reading_data)
            session.add(reading)
            session.flush()

            for sample in thermocouple_samples:
                if sample is None:
                    continue
                sample_payload = {"reading_id": reading.id, **sample}
                tc_reading = ThermocoupleReading(**sample_payload)
                session.add(tc_reading)

            session.commit()
            session.refresh(reading)
            session.expunge(reading)
            return reading
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def create_reading_async(
        self,
        reading_data: Dict[str, Any],
        thermocouple_samples: Iterable[Dict[str, Any]],
    ) -> Reading:
        return await asyncio.to_thread(self.create_reading, reading_data, list(thermocouple_samples))
