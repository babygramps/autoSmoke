"""Shared pytest fixtures for backend tests."""

import pytest

from core.container import ServiceContainer


@pytest.fixture
def service_container() -> ServiceContainer:
    """Provide a fresh service container for each test."""

    return ServiceContainer.build()
