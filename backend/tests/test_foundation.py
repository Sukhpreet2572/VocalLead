from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import ROOT, Settings
from app.database import build_engine, database_connected
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'test.db'}",
                    app_env="development", google_api_key="test-secret-do-not-expose")


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


def test_root(client):
    assert client.get("/").json() == {"name": "VocaLead AI API", "version": "0.1.0", "docs": "/docs"}


def test_health_and_docs(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "vocalead-api", "version": "0.1.0"}
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_ready(client):
    assert client.get("/api/v1/ready").json() == {"status": "ready", "database": "connected"}


def test_ready_failure(client):
    with patch("app.api.routes.system.database_connected", return_value=False):
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Database unavailable"
    assert client.get("/api/v1/health").status_code == 200


def test_database_failure_is_sanitized():
    with patch("sqlalchemy.orm.Session.execute", side_effect=OperationalError("secret", {}, Exception("secret"))):
        from sqlalchemy.orm import Session
        assert database_connected(Session()) is False


def test_status_and_no_secrets(client, settings):
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "connected"
    assert body["integrations"]["gemini"] == {"configured": True, "connectivity": "not_verified"}
    for value in (settings.google_api_key.get_secret_value(), settings.database_url.get_secret_value()):
        assert value not in response.text
    with patch("app.api.routes.system.database_connected", return_value=False):
        assert client.get("/api/v1/system/status").json()["database"] == "unavailable"


def test_diagnostics_disabled_in_production(settings):
    settings.app_env = "production"
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/system/status").status_code == 404


def test_configuration(monkeypatch, tmp_path):
    env = tmp_path / "settings.env"
    env.write_text('API_PORT=8123\nCORS_ORIGINS=["http://localhost:5173"]\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == ROOT / ".env"
    assert Settings(_env_file=env).api_port == 8123
    monkeypatch.setenv("API_PORT", "8124")
    assert Settings(_env_file=env).api_port == 8124
    with pytest.raises(ValidationError):
        Settings(api_port=70000)
    with pytest.raises(ValidationError):
        Settings(database_url="")


def test_relative_sqlite_path(settings):
    settings.database_url = Settings(_env_file=None).database_url
    engine = build_engine(settings)
    assert Path(engine.url.database).is_absolute()
    engine.dispose()


def test_cors(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers
