"""Repository for persisting system events."""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from sqlmodel import Session

from db.models import Event
from db.session import get_session_sync

SessionFactory = Callable[[], Session]


class EventsRepository:
    """Encapsulates creation of system events."""

    def __init__(self, session_factory: SessionFactory = get_session_sync) -> None:
        self._session_factory = session_factory

    def _create_session(self) -> Session:
        session = self._session_factory()
        if isinstance(session, Session):
            return session
        return session  # type: ignore[return-value]

    def log_event(self, kind: str, message: str, meta_json: Optional[str] = None) -> Event:
        session = self._create_session()
        try:
            event = Event(kind=kind, message=message, meta_json=meta_json)
            session.add(event)
            session.commit()
            session.refresh(event)
            session.expunge(event)
            return event
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def log_event_async(self, kind: str, message: str, meta_json: Optional[str] = None) -> Event:
        return await asyncio.to_thread(self.log_event, kind, message, meta_json)
