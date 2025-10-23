"""Repository for interacting with settings stored in the database."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from sqlmodel import Session

from db.models import Settings as DBSettings
from db.session import get_session_sync

SessionFactory = Callable[[], Session]


class SettingsRepository:
    """Encapsulates CRUD operations for system settings."""

    def __init__(self, session_factory: SessionFactory = get_session_sync) -> None:
        self._session_factory = session_factory

    def _create_session(self) -> Session:
        session = self._session_factory()
        if isinstance(session, Session):
            return session
        # Support session factories that return context managers
        return session  # type: ignore[return-value]

    def get_settings(self, ensure: bool = False) -> Optional[DBSettings]:
        """Return the singleton settings record.

        Args:
            ensure: When True, create the record if it does not yet exist.
        """
        session = self._create_session()
        try:
            db_settings = session.get(DBSettings, 1)
            if ensure and not db_settings:
                db_settings = DBSettings()
                session.add(db_settings)
                session.commit()
                session.refresh(db_settings)
            if db_settings:
                session.expunge(db_settings)
            return db_settings
        finally:
            session.close()

    async def get_settings_async(self, ensure: bool = False) -> Optional[DBSettings]:
        """Async wrapper for :meth:`get_settings`."""
        return await asyncio.to_thread(self.get_settings, ensure)

    def update_settings(self, updates: Dict[str, Any]) -> DBSettings:
        """Apply updates to the singleton settings record."""
        session = self._create_session()
        try:
            db_settings = session.get(DBSettings, 1)
            if not db_settings:
                db_settings = DBSettings()
                session.add(db_settings)

            for field, value in updates.items():
                if hasattr(db_settings, field):
                    setattr(db_settings, field, value)

            if "updated_at" not in updates:
                db_settings.updated_at = datetime.utcnow()

            session.add(db_settings)
            session.commit()
            session.refresh(db_settings)
            session.expunge(db_settings)
            return db_settings
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def update_settings_async(self, updates: Dict[str, Any]) -> DBSettings:
        """Async wrapper for :meth:`update_settings`."""
        return await asyncio.to_thread(self.update_settings, updates)

    def reset_settings(self) -> DBSettings:
        """Reset settings to default values."""
        defaults = DBSettings()
        update_payload = defaults.model_dump(
            exclude={"singleton_id", "created_at", "updated_at"},
        )
        return self.update_settings(update_payload)

    async def reset_settings_async(self) -> DBSettings:
        """Async wrapper for :meth:`reset_settings`."""
        return await asyncio.to_thread(self.reset_settings)

    def set_setpoint(self, setpoint_f: float, setpoint_c: float) -> DBSettings:
        """Persist the current temperature setpoint."""
        return self.update_settings({
            "setpoint_f": setpoint_f,
            "setpoint_c": setpoint_c,
        })

    async def set_setpoint_async(self, setpoint_f: float, setpoint_c: float) -> DBSettings:
        return await asyncio.to_thread(self.set_setpoint, setpoint_f, setpoint_c)

    def set_pid_gains(self, kp: float, ki: float, kd: float) -> DBSettings:
        """Persist PID gain values."""
        return self.update_settings({
            "kp": kp,
            "ki": ki,
            "kd": kd,
        })

    def set_timing_params(self, min_on_s: int, min_off_s: int, hyst_c: float, time_window_s: Optional[int] = None) -> DBSettings:
        updates: Dict[str, Any] = {
            "min_on_s": min_on_s,
            "min_off_s": min_off_s,
            "hyst_c": hyst_c,
        }
        if time_window_s is not None:
            updates["time_window_s"] = time_window_s
        return self.update_settings(updates)

    def set_control_mode(self, mode: str) -> DBSettings:
        return self.update_settings({"control_mode": mode})

    def set_adaptive_pid_enabled(self, enabled: bool) -> DBSettings:
        return self.update_settings({"adaptive_pid_enabled": enabled})

    async def set_adaptive_pid_enabled_async(self, enabled: bool) -> DBSettings:
        return await asyncio.to_thread(self.set_adaptive_pid_enabled, enabled)

    def get_webhook_url(self) -> Optional[str]:
        settings = self.get_settings()
        return settings.webhook_url if settings else None

    async def get_webhook_url_async(self) -> Optional[str]:
        settings = await self.get_settings_async()
        return settings.webhook_url if settings else None
