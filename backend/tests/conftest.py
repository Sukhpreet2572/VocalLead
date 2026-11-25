"""Remove inherited application settings before collection imports app.main."""
import pytest
from app.core.config import Settings

_environment = pytest.MonkeyPatch()


def pytest_configure() -> None:
    for name in Settings.model_fields:
        _environment.delenv(name.upper(), raising=False)


def pytest_unconfigure() -> None:
    _environment.undo()
