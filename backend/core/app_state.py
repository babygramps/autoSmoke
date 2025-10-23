"""Helpers for storing shared services on the FastAPI application state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


SERVICE_CONTAINER_KEY = "service_container"


if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from .container import ServiceContainer


def set_service_container(app: Any, container: "ServiceContainer") -> None:
    """Attach the service container to the FastAPI application state."""

    setattr(app.state, SERVICE_CONTAINER_KEY, container)


def get_service_container(app: Any) -> "ServiceContainer":
    """Retrieve the service container from the FastAPI application state."""

    container = getattr(app.state, SERVICE_CONTAINER_KEY, None)
    if container is None:
        raise RuntimeError("Service container has not been initialised")
    return container
