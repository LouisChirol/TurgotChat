from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.api.main as main

RUNNING = {"message": "Turgot API is running"}


class _Collection:
    def __init__(self, count=3, boom: BaseException | None = None):
        self._count = count
        self._boom = boom

    def count(self):
        if self._boom:
            raise self._boom
        return self._count


def _agent(collection: _Collection):
    return SimpleNamespace(
        retriever=SimpleNamespace(vector_store=SimpleNamespace(_collection=collection))
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(main, "TurgotGraphAgent", lambda: _agent(_Collection()))
    monkeypatch.setenv("MAINTENANCE_STATUS_PATH", str(tmp_path / "missing-status.json"))
    with TestClient(main.app) as test_client:
        yield test_client


def test_root_stays_running_when_chroma_answers(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == RUNNING


def test_health_reports_chroma_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {**RUNNING, "chroma": "ok"}


def test_root_and_health_fail_closed_without_leaking_the_exception(
    monkeypatch: pytest.MonkeyPatch,
):
    boom = RuntimeError("sqlite locked at /app/database/chroma_db on redis:6379")
    monkeypatch.setattr(main, "TurgotGraphAgent", lambda: _agent(_Collection(boom=boom)))
    with TestClient(main.app) as client:
        for path in ("/", "/health"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json() == {"detail": "Chroma unavailable"}
            assert "/app/database" not in response.text
            assert "redis" not in response.text
            assert "locked" not in response.text


def test_health_data_is_sanitized_and_cache_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    status_path = tmp_path / "maintenance_status.json"
    status_path.write_text(
        """
        {
          "jobs": {
            "service_public": {
              "last_run_at": "2026-11-04T03:20:00Z",
              "last_success_at": "2026-10-28T03:20:00Z",
              "status": "error",
              "duration_seconds": 40,
              "error": "rsync /home/ubuntu/turgot/database/chroma_db token=sekrit"
            }
          },
          "newest_backup_at": "2026-11-04T03:00:12Z",
          "collections": {"service_public": 1200, "bofip": 80},
          "updated_at": "2026-11-04T03:20:00Z",
          "logfile": "/home/ubuntu/turgot/logs/db_update.log"
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "TurgotGraphAgent", lambda: _agent(_Collection()))
    monkeypatch.setenv("MAINTENANCE_STATUS_PATH", str(status_path))
    with TestClient(main.app) as client:
        response = client.get("/health/data")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["newest_backup_at"] == "2026-11-04T03:00:12Z"
    assert body["collections"] == {"bofip": 80, "service_public": 1200}
    job = body["jobs"]["service_public"]
    assert job["status"] == "error"
    assert job["duration_seconds"] == 40
    assert job["last_success_at"] == "2026-10-28T03:20:00Z"
    assert "sekrit" not in response.text
    assert "/home/ubuntu" not in response.text
    assert "logfile" not in body
    assert body["jobs"]["bofip"]["status"] == "unknown"
    assert body["jobs"]["backup"]["status"] == "unknown"
    assert body["jobs"]["verify"]["status"] == "unknown"


def test_health_data_missing_or_corrupt_file_is_an_empty_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    missing = tmp_path / "nope.json"
    monkeypatch.setenv("MAINTENANCE_STATUS_PATH", str(missing))
    monkeypatch.setattr(main, "TurgotGraphAgent", lambda: _agent(_Collection()))
    with TestClient(main.app) as client:
        missing_response = client.get("/health/data")
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("{not json", encoding="utf-8")
        monkeypatch.setenv("MAINTENANCE_STATUS_PATH", str(corrupt))
        corrupt_response = client.get("/health/data")

    assert missing_response.status_code == 200
    assert missing_response.json()["jobs"]["verify"]["status"] == "unknown"
    assert missing_response.json()["collections"] == {}
    assert corrupt_response.status_code == 200
    assert corrupt_response.json()["newest_backup_at"] is None
    assert "/home" not in corrupt_response.text
