"""Read and write the maintenance status file.

The cron jobs on the VPS call this module with system ``python3`` (stdlib
only). The backend serves the same document from ``GET /health/data``.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

JOB_NAMES = ("service_public", "bofip", "backup", "verify")
MAX_ERROR_LEN = 300

_BACKUP_NAME = re.compile(r"^chroma_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})$")
_COUNT_LINE = re.compile(r"^OK: ([a-z][a-z0-9_]{0,63}) count=(\d+)\s*$")
_COLLECTION_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ISO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Absolute filesystem paths. URL paths stay (the slash is preceded by a host
# character, not by whitespace or the start of the string).
_ABS_PATH = re.compile(
    r"(?:(?<=\s)|(?<=^))"
    r"((?:/[A-Za-z0-9._@+-]+){2,}|[A-Za-z]:\\[^\s]+|~/(?:[^\s/]+/?)+)"
)
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_INTERNAL_HOST = re.compile(
    r"\b(?:localhost|redis|backend|db_updater|turgot-backend|turgot-frontend)"
    r"(?::\d+)?\b"
)
_DOT_INTERNAL = re.compile(
    r"\b(?:[A-Za-z0-9-]+\.)+(?:local|internal|lan|home|svc|cluster|localdomain)\b"
)
_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|token|password|secret|authorization)\b\s*[=:]\s*\S+"
)
_USERINFO = re.compile(r"(https?://)[^\s/@]+:[^\s/@]+@")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def empty_job() -> dict[str, Any]:
    return {
        "last_run_at": None,
        "last_success_at": None,
        "status": "unknown",
        "duration_seconds": None,
        "error": None,
    }


def empty_status() -> dict[str, Any]:
    return {
        "jobs": {name: empty_job() for name in JOB_NAMES},
        "newest_backup_at": None,
        "collections": {},
        "updated_at": None,
    }


def default_status_path() -> Path:
    override = os.environ.get("MAINTENANCE_STATUS_PATH")
    if override:
        return Path(override)
    if os.path.exists("/.dockerenv"):
        return Path("/app/logs/maintenance_status.json")
    return Path(__file__).resolve().parents[1] / "logs" / "maintenance_status.json"


def sanitize_error(message: str | None) -> str | None:
    """Collapse whitespace and drop paths, internal hosts, and secrets."""
    if message is None:
        return None
    text = " ".join(str(message).split())
    if not text:
        return None
    text = _USERINFO.sub(r"\1", text)
    text = _SECRET.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    text = _ABS_PATH.sub("[path]", text)
    text = _IPV4.sub("[ip]", text)
    text = _INTERNAL_HOST.sub("[host]", text)
    text = _DOT_INTERNAL.sub("[host]", text)
    if len(text) > MAX_ERROR_LEN:
        text = text[: MAX_ERROR_LEN - 3].rstrip() + "..."
    return text or None


def sanitize_collections(value: Any) -> dict[str, int]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, Mapping):
        return {}
    clean: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not _COLLECTION_NAME.match(key):
            continue
        if isinstance(raw, bool) or not isinstance(raw, int):
            continue
        if raw < 0:
            continue
        clean[key] = raw
    return clean


def backup_timestamp_from_name(name: str) -> str | None:
    match = _BACKUP_NAME.match(name.strip())
    if not match:
        return None
    day, hour, minute, second = match.groups()
    if int(hour) > 23 or int(minute) > 59 or int(second) > 59:
        return None
    return f"{day}T{hour}:{minute}:{second}Z"


def newest_backup_timestamp(names: list[str]) -> str | None:
    stamps = [
        stamp
        for stamp in (backup_timestamp_from_name(name) for name in names)
        if stamp
    ]
    if not stamps:
        return None
    return max(stamps)


def counts_from_log(text: str) -> dict[str, int]:
    """Parse ``OK: <collection> count=<n>`` lines printed by the Chroma verify."""
    found: dict[str, int] = {}
    for line in text.splitlines():
        match = _COUNT_LINE.match(line.strip())
        if match and _COLLECTION_NAME.match(match.group(1)):
            found[match.group(1)] = int(match.group(2))
    return found


def _coerce_job(incoming: Any) -> dict[str, Any]:
    job = empty_job()
    if not isinstance(incoming, dict):
        return job
    for key in ("last_run_at", "last_success_at"):
        value = incoming.get(key)
        if isinstance(value, str) and _ISO_TS.match(value):
            job[key] = value
    status = incoming.get("status")
    if status in ("ok", "error", "unknown"):
        job["status"] = status
    duration = incoming.get("duration_seconds")
    if isinstance(duration, int) and not isinstance(duration, bool) and duration >= 0:
        job["duration_seconds"] = duration
    error = incoming.get("error")
    if isinstance(error, str):
        job["error"] = sanitize_error(error)
    if job["status"] == "ok":
        job["error"] = None
    return job


def _coerce_stored(parsed: Any) -> dict[str, Any]:
    base = empty_status()
    if not isinstance(parsed, dict):
        return base
    jobs = parsed.get("jobs")
    if isinstance(jobs, dict):
        for name in JOB_NAMES:
            if name in jobs:
                base["jobs"][name] = _coerce_job(jobs.get(name))
    backup = parsed.get("newest_backup_at")
    if isinstance(backup, str) and _ISO_TS.match(backup):
        base["newest_backup_at"] = backup
    base["collections"] = sanitize_collections(parsed.get("collections"))
    updated = parsed.get("updated_at")
    if isinstance(updated, str) and _ISO_TS.match(updated):
        base["updated_at"] = updated
    return base


def read_status(path: Path) -> dict[str, Any]:
    """Return stored JSON, or an empty document if the file is missing or unreadable."""
    if not path.is_file():
        return empty_status()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return empty_status()
    return parsed if isinstance(parsed, dict) else empty_status()


def public_view(data: Any) -> dict[str, Any]:
    """Whitelist fields safe to publish. Drops paths, hosts, and unknown keys."""
    clean = _coerce_stored(data)
    for job in clean["jobs"].values():
        job["error"] = sanitize_error(job.get("error"))
        if job["status"] == "ok":
            job["error"] = None
    return clean


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    payload = json.dumps(public_view(data), indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f"{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def record_job(
    path: Path,
    job: str,
    status: str,
    duration_seconds: int,
    error: str | None = None,
    *,
    now: str | None = None,
    collections: Mapping[str, Any] | None = None,
    newest_backup_at: str | None = None,
) -> dict[str, Any]:
    """Update one job and refresh shared backup/collection fields when provided."""
    if job not in JOB_NAMES:
        raise ValueError(f"unknown job: {job}")
    if status not in ("ok", "error"):
        raise ValueError(f"unknown status: {status}")
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int):
        raise ValueError("duration must be an integer number of seconds")
    if duration_seconds < 0:
        raise ValueError("duration must be >= 0")

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    stamp = now or utc_now_iso()
    if not _ISO_TS.match(stamp):
        raise ValueError("timestamp must be UTC ISO-8601")

    with open(lock_path, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            data = _coerce_stored(read_status(path))
            slot = data["jobs"][job]
            slot["last_run_at"] = stamp
            slot["status"] = status
            slot["duration_seconds"] = duration_seconds
            if status == "ok":
                slot["last_success_at"] = stamp
                slot["error"] = None
            else:
                slot["error"] = sanitize_error(error) or "job failed"
            if isinstance(newest_backup_at, str) and _ISO_TS.match(newest_backup_at):
                current = data.get("newest_backup_at")
                if current is None or newest_backup_at >= current:
                    data["newest_backup_at"] = newest_backup_at
            if collections is not None:
                merged = dict(data.get("collections") or {})
                merged.update(sanitize_collections(collections))
                data["collections"] = merged
            data["updated_at"] = stamp
            _atomic_write(path, data)
            return public_view(data)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _cmd_record(args: argparse.Namespace) -> int:
    collections = None
    if args.collections:
        collections = json.loads(args.collections)
    record_job(
        Path(args.file),
        args.job,
        args.status,
        args.duration,
        args.error or None,
        collections=collections,
        newest_backup_at=args.newest_backup_at,
    )
    return 0


def _cmd_newest_backup() -> int:
    names = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    stamp = newest_backup_timestamp(names)
    if stamp:
        print(stamp)
    return 0


def _cmd_counts_from_log(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    print(json.dumps(counts_from_log(text), sort_keys=True))
    return 0


def _cmd_sanitize_error() -> int:
    """Print one line safe to hand to a third party. Never echoes the raw input."""
    try:
        message = sys.stdin.read(8192)
    except UnicodeError:
        print("job failed")
        return 0
    print(sanitize_error(message) or "job failed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update the maintenance status file")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record")
    record.add_argument("--file", required=True)
    record.add_argument("--job", required=True)
    record.add_argument("--status", required=True, choices=("ok", "error"))
    record.add_argument("--duration", required=True, type=int)
    record.add_argument("--error", default="")
    record.add_argument("--newest-backup-at")
    record.add_argument("--collections")

    sub.add_parser("newest-backup")

    counts = sub.add_parser("counts-from-log")
    counts.add_argument("--file", required=True)

    sub.add_parser("sanitize-error")

    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            return _cmd_record(args)
        if args.command == "newest-backup":
            return _cmd_newest_backup()
        if args.command == "counts-from-log":
            return _cmd_counts_from_log(Path(args.file))
        if args.command == "sanitize-error":
            return _cmd_sanitize_error()
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"maintenance status error: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
