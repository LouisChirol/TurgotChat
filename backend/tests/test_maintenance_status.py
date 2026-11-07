import json
import subprocess
from pathlib import Path

from app.maintenance_status import (
    backup_timestamp_from_name,
    counts_from_log,
    empty_status,
    newest_backup_timestamp,
    public_view,
    record_job,
    sanitize_error,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_SCRIPT = REPO_ROOT / "backend" / "app" / "maintenance_status.py"
HOST_PYTHON = "/usr/bin/python3"


def test_record_success_updates_one_job_and_keeps_the_other(tmp_path: Path):
    path = tmp_path / "status.json"
    record_job(
        path,
        "bofip",
        "ok",
        90,
        now="2026-10-01T04:10:00Z",
        newest_backup_at="2026-10-01T04:00:00Z",
        collections={"bofip": 10, "service_public": 20},
    )
    updated = record_job(
        path,
        "service_public",
        "error",
        15,
        error="rsync failed reading /home/ubuntu/turgot/database/chroma_db",
        now="2026-11-04T03:20:00Z",
    )

    assert updated["jobs"]["bofip"]["status"] == "ok"
    assert updated["jobs"]["bofip"]["last_success_at"] == "2026-10-01T04:10:00Z"
    assert updated["jobs"]["bofip"]["duration_seconds"] == 90
    service_public = updated["jobs"]["service_public"]
    assert service_public["status"] == "error"
    assert service_public["last_run_at"] == "2026-11-04T03:20:00Z"
    assert service_public["last_success_at"] is None
    assert service_public["duration_seconds"] == 15
    assert "/home/ubuntu" not in service_public["error"]
    assert "[path]" in service_public["error"]
    assert updated["newest_backup_at"] == "2026-10-01T04:00:00Z"
    assert updated["collections"] == {"bofip": 10, "service_public": 20}
    assert updated["updated_at"] == "2026-11-04T03:20:00Z"


def test_failure_keeps_previous_success_and_newer_backup_wins(tmp_path: Path):
    path = tmp_path / "status.json"
    record_job(path, "backup", "ok", 4, now="2026-11-04T03:00:00Z")
    record_job(
        path,
        "backup",
        "error",
        2,
        error="chroma backup rsync failed",
        now="2026-11-11T03:00:00Z",
        newest_backup_at="2026-11-01T03:00:00Z",
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["jobs"]["backup"]["last_success_at"] == "2026-11-04T03:00:00Z"
    assert stored["jobs"]["backup"]["last_run_at"] == "2026-11-11T03:00:00Z"
    assert stored["jobs"]["backup"]["error"] == "chroma backup rsync failed"
    assert stored["newest_backup_at"] == "2026-11-01T03:00:00Z"

    record_job(
        path,
        "backup",
        "ok",
        5,
        now="2026-11-18T03:00:00Z",
        newest_backup_at="2026-10-01T03:00:00Z",
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["newest_backup_at"] == "2026-11-01T03:00:00Z"
    assert stored["jobs"]["backup"]["error"] is None
    assert stored["jobs"]["backup"]["last_success_at"] == "2026-11-18T03:00:00Z"


def test_collections_merge_drops_unsafe_keys(tmp_path: Path):
    path = tmp_path / "status.json"
    record_job(
        path,
        "verify",
        "ok",
        1,
        now="2026-11-04T03:30:00Z",
        collections={"service_public": 5, "../etc/passwd": 1, "Bad": 2},
    )
    record_job(
        path,
        "verify",
        "ok",
        1,
        now="2026-11-04T03:40:00Z",
        collections={"bofip": 9, "service_public": "nope", "ok_name": True},
    )
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["collections"] == {"bofip": 9, "service_public": 5}


def test_sanitize_error_keeps_public_url_and_strips_secrets():
    message = (
        "curl https://user:secret@turgot.louischirol.fr/api/ failed; "
        "token=abc123 host redis:6379 db.internal ip 10.1.2.3 "
        "file /app/database/chroma_db"
    )
    clean = sanitize_error(message)
    assert clean is not None
    assert "secret@" not in clean
    assert "abc123" not in clean
    assert "10.1.2.3" not in clean
    assert "redis:6379" not in clean
    assert "db.internal" not in clean
    assert "/app/database" not in clean
    assert "https://turgot.louischirol.fr/api/" in clean
    assert sanitize_error("x" * 500) is not None
    assert len(sanitize_error("x" * 500) or "") <= 300


def test_public_view_drops_unknown_fields_and_paths():
    raw = {
        "jobs": {
            "backup": {
                "last_run_at": "2026-11-04T03:00:00Z",
                "last_success_at": None,
                "status": "error",
                "duration_seconds": 3,
                "error": "see /var/lib/turgot/chroma",
                "logfile": "/home/ubuntu/turgot/logs/db_update.log",
            }
        },
        "newest_backup_at": "not-a-timestamp",
        "collections": {"service_public": 4, "has space": 1},
        "updated_at": "2026-11-04T03:00:01Z",
        "status_path": "/home/ubuntu/turgot/backend/logs/maintenance_status.json",
        "hostname": "vps.internal",
    }
    public = public_view(raw)
    assert "status_path" not in public
    assert "hostname" not in public
    assert "logfile" not in public["jobs"]["backup"]
    assert public["newest_backup_at"] is None
    assert public["collections"] == {"service_public": 4}
    assert "/var/lib" not in json.dumps(public)
    assert "/home/ubuntu" not in json.dumps(public)
    assert public["jobs"]["service_public"]["status"] == "unknown"
    assert public_view("nope") == empty_status()


def test_backup_names_and_verify_log_lines():
    assert backup_timestamp_from_name("chroma_2026-11-04_03-15-09") == (
        "2026-11-04T03:15:09Z"
    )
    assert backup_timestamp_from_name("chroma_../../etc") is None
    assert backup_timestamp_from_name("chroma_2026-11-04_99-00-00") is None
    assert (
        newest_backup_timestamp(
            [
                "chroma_not-a-date",
                "chroma_2026-10-01_03-00-00",
                "chroma_2026-11-04_03-15-09",
                "../chroma_2026-12-01_00-00-00",
            ]
        )
        == "2026-11-04T03:15:09Z"
    )
    text = "noise\nOK: service_public count=1200\nOK: bofip count=80\nOK: ../x count=1\n"
    assert counts_from_log(text) == {"bofip": 80, "service_public": 1200}


def test_host_python_cli_record_and_newest_backup(tmp_path: Path):
    status_path = tmp_path / "nested" / "status.json"
    log_path = tmp_path / "job.log"
    log_path.write_text("OK: service_public count=7\n", encoding="utf-8")

    recorded = subprocess.run(
        [
            HOST_PYTHON,
            str(STATUS_SCRIPT),
            "record",
            "--file",
            str(status_path),
            "--job",
            "service_public",
            "--status",
            "ok",
            "--duration",
            "12",
            "--collections",
            subprocess.check_output(
                [HOST_PYTHON, str(STATUS_SCRIPT), "counts-from-log", "--file", str(log_path)],
                text=True,
            ).strip(),
            "--newest-backup-at",
            "2026-11-04T03:15:09Z",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert recorded.returncode == 0
    stored = json.loads(status_path.read_text(encoding="utf-8"))
    assert stored["jobs"]["service_public"]["duration_seconds"] == 12
    assert stored["collections"] == {"service_public": 7}
    assert stored["newest_backup_at"] == "2026-11-04T03:15:09Z"

    names = "chroma_2026-10-01_03-00-00\nchroma_not-a-date\nchroma_2026-11-04_03-15-09\n"
    newest = subprocess.run(
        [HOST_PYTHON, str(STATUS_SCRIPT), "newest-backup"],
        input=names,
        check=True,
        capture_output=True,
        text=True,
    )
    assert newest.stdout.strip() == "2026-11-04T03:15:09Z"

    rejected = subprocess.run(
        [
            HOST_PYTHON,
            str(STATUS_SCRIPT),
            "record",
            "--file",
            str(status_path),
            "--job",
            "not-a-job",
            "--status",
            "ok",
            "--duration",
            "1",
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 1
    assert "ValueError" in rejected.stderr
    assert "not-a-job" not in rejected.stderr


def test_sanitize_error_cli_strips_secrets_and_paths():
    cleaned = subprocess.run(
        [HOST_PYTHON, str(STATUS_SCRIPT), "sanitize-error"],
        input="token=sekrit at /home/ubuntu/turgot\n",
        check=True,
        capture_output=True,
        text=True,
    )
    assert cleaned.stderr == ""
    assert "sekrit" not in cleaned.stdout
    assert "/home/ubuntu" not in cleaned.stdout
    assert "token=[redacted]" in cleaned.stdout
    assert "[path]" in cleaned.stdout

    empty = subprocess.run(
        [HOST_PYTHON, str(STATUS_SCRIPT), "sanitize-error"],
        input="   \n",
        check=True,
        capture_output=True,
        text=True,
    )
    assert empty.stdout.strip() == "job failed"
