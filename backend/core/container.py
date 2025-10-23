"""Application service wiring for FastAPI dependency injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Request, WebSocket

from core.app_state import get_service_container, set_service_container
from core.alerts import AlertManager
from core.controller import SmokerController
from db.repositories import EventsRepository, ReadingsRepository, SettingsRepository
from ws.manager import ConnectionManager


@dataclass
class ServiceContainer:
    """Holds shared application services and orchestrates their lifecycle."""

    settings_repo: SettingsRepository
    readings_repo: ReadingsRepository
    events_repo: EventsRepository
    alert_manager: AlertManager
    controller: SmokerController
    connection_manager: ConnectionManager

    @classmethod
    def build(
        cls,
        *,
        settings_repo: Optional[SettingsRepository] = None,
        readings_repo: Optional[ReadingsRepository] = None,
        events_repo: Optional[EventsRepository] = None,
        alert_manager: Optional[AlertManager] = None,
        controller: Optional[SmokerController] = None,
        connection_manager: Optional[ConnectionManager] = None,
    ) -> "ServiceContainer":
        """Create a container with optional dependency overrides."""

        settings_repo = settings_repo or SettingsRepository()
        readings_repo = readings_repo or ReadingsRepository()
        events_repo = events_repo or EventsRepository()
        alert_manager = alert_manager or AlertManager()
        controller = controller or SmokerController(
            settings_repository=settings_repo,
            readings_repository=readings_repo,
            events_repository=events_repo,
            alert_manager=alert_manager,
        )
        connection_manager = connection_manager or ConnectionManager(
            controller=controller,
            alert_manager=alert_manager,
        )

        return cls(
            settings_repo=settings_repo,
            readings_repo=readings_repo,
            events_repo=events_repo,
            alert_manager=alert_manager,
            controller=controller,
            connection_manager=connection_manager,
        )

    async def startup(self) -> None:
        """Start background services when the application boots."""

        await self.connection_manager.start_broadcasting()

    async def shutdown(self) -> None:
        """Shutdown background services when the application stops."""

        await self.connection_manager.stop_broadcasting()
        await self.alert_manager.cleanup()


def initialise_services(app) -> ServiceContainer:
    """Create and attach the service container to the FastAPI application."""

    container = ServiceContainer.build()
    set_service_container(app, container)
    return container


def get_container(request: Request) -> ServiceContainer:
    """FastAPI dependency that returns the shared service container."""

    return get_service_container(request.app)


def get_controller(request: Request) -> SmokerController:
    """FastAPI dependency that returns the singleton controller instance."""

    return get_container(request).controller


def get_alert_manager(request: Request) -> AlertManager:
    """FastAPI dependency that returns the alert manager."""

    return get_container(request).alert_manager


def get_settings_repository(request: Request) -> SettingsRepository:
    """FastAPI dependency for the settings repository."""

    return get_container(request).settings_repo


def get_readings_repository(request: Request) -> ReadingsRepository:
    """FastAPI dependency for the readings repository."""

    return get_container(request).readings_repo


def get_events_repository(request: Request) -> EventsRepository:
    """FastAPI dependency for the events repository."""

    return get_container(request).events_repo


def get_connection_manager(websocket: WebSocket) -> ConnectionManager:
    """FastAPI dependency for retrieving the WebSocket connection manager."""

    return get_service_container(websocket.app).connection_manager
