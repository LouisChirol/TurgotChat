import json
import os
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON = REPO_ROOT / "scripts" / "maintenance_common.sh"
PING_URL = "https://hc.example/super-secret-uuid"


def _run(script: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd or REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env={
            **os.environ,
            "HC_SERVICE_PUBLIC_URL": "",
            "HC_BOFIP_URL": "",
            "HC_BACKUP_URL": "",
            "HC_VERIFY_URL": "",
        },
    )


def test_maintenance_scripts_pass_bash_n():
    for name in (
        "maintenance_common.sh",
        "cron_update_docker.sh",
        "cron_bofip_update_docker.sh",
    ):
        result = subprocess.run(
            ["bash", "-n", str(REPO_ROOT / "scripts" / name)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_hc_ping_never_fails_the_caller_and_hides_the_url(tmp_path: Path):
    curl_log = tmp_path / "curl.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_bin = bin_dir / "curl"
    curl_bin.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            printf 'ARGS:%s\\n' "$*" >> "{curl_log}"
            case "$*" in
              *--data-binary*) cat >> "{curl_log}" ;;
            esac
            printf '\\n---\\n' >> "{curl_log}"
            exit 9
            """
        ),
        encoding="utf-8",
    )
    curl_bin.chmod(0o755)
    job_log = tmp_path / "job.log"
    job_log.write_text(
        "earlier token=keep-me-out should not be uploaded\n"
        "ERROR: disk full at /home/ubuntu/turgot token=sekrit\n",
        encoding="utf-8",
    )

    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        export PATH="{bin_dir}:$PATH"
        export CURL_LOG="{curl_log}"
        # shellcheck disable=SC1091
        source "{COMMON}"
        maintenance_hc_ping "" fail "{job_log}"
        maintenance_hc_ping "{PING_URL}/" start
        maintenance_hc_ping "{PING_URL}" success
        maintenance_hc_ping "{PING_URL}" fail "{job_log}"
        echo PING_OK
        """
    )
    result = _run(script)
    assert result.returncode == 0, result.stderr
    assert "PING_OK" in result.stdout
    assert PING_URL not in result.stdout
    calls = curl_log.read_text(encoding="utf-8")
    assert calls.count(PING_URL) == 3
    assert f"{PING_URL}/start" in calls
    assert f"{PING_URL}/fail" in calls
    assert "disk full" in calls
    assert "token=[redacted]" in calls
    assert "[path]" in calls
    assert "sekrit" not in calls
    assert "keep-me-out" not in calls
    assert "/home/ubuntu" not in calls
    # success ping is the base URL, not /success
    assert f"{PING_URL}/success" not in calls


def test_record_status_from_shell_uses_log_counts_not_docker(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "backend" / "app").mkdir(parents=True)
    (repo / "database" / "backups" / "chroma_2026-10-01_03-00-00").mkdir(parents=True)
    (repo / "database" / "backups" / "chroma_not-a-date").mkdir()
    (repo / "database" / "backups" / "chroma_2026-11-04_03-15-09").mkdir()
    os.symlink(
        REPO_ROOT / "backend" / "app" / "maintenance_status.py",
        repo / "backend" / "app" / "maintenance_status.py",
    )
    log_path = repo / "logs" / "job.log"
    log_path.parent.mkdir()
    log_path.write_text(
        "OK: service_public count=11\nOK: bofip count=4\n",
        encoding="utf-8",
    )
    status_path = tmp_path / "status.json"
    docker_log = tmp_path / "docker.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_bin = bin_dir / "docker"
    docker_bin.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            printf '%s\\n' "$*" >> "{docker_log}"
            exit 1
            """
        ),
        encoding="utf-8",
    )
    docker_bin.chmod(0o755)

    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        export PATH="{bin_dir}:$PATH"
        export REPO="{repo}"
        export MAINTENANCE_STATUS_PATH="{status_path}"
        export MAINTENANCE_LOGFILE="{log_path}"
        # shellcheck disable=SC1091
        source "{COMMON}"
        maintenance_record_status service_public error 33 "token=should-not-stick" 1
        """
    )
    result = _run(script)
    assert result.returncode == 0, result.stderr
    assert not docker_log.exists()
    stored = json.loads(status_path.read_text(encoding="utf-8"))
    assert stored["jobs"]["service_public"]["status"] == "error"
    assert stored["jobs"]["service_public"]["duration_seconds"] == 33
    assert stored["jobs"]["service_public"]["error"] == "token=[redacted]"
    assert stored["collections"] == {"bofip": 4, "service_public": 11}
    assert stored["newest_backup_at"] == "2026-11-04T03:15:09Z"
    assert "should-not-stick" not in status_path.read_text(encoding="utf-8")


def _fake_tools(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_log = tmp_path / "curl.log"
    (bin_dir / "curl").write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            printf '%s\\n' "$*" >> "{curl_log}"
            case "$*" in
              *--data-binary*) cat >> "{curl_log}" ;;
            esac
            exit 9
            """
        ),
        encoding="utf-8",
    )
    (bin_dir / "docker").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for tool in ("curl", "docker"):
        (bin_dir / tool).chmod(0o755)
    return bin_dir


def test_flock_job_pings_start_and_success_without_logging_the_url(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = _fake_tools(tmp_path)
    lock = tmp_path / "job.lock"
    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        export PATH="{bin_dir}:$PATH"
        export REPO="{repo}"
        export HC_SERVICE_PUBLIC_URL="{PING_URL}"
        export HC_BOFIP_URL=""
        export HC_BACKUP_URL=""
        export HC_VERIFY_URL=""
        export MAINTENANCE_STATUS_PATH="{tmp_path / "status.json"}"
        # shellcheck disable=SC1091
        source "{COMMON}"
        run_ok_job() {{ return 0; }}
        maintenance_with_flock db_update "{lock}" run_ok_job
        """
    )
    result = _run(script)
    assert result.returncode == 0, result.stderr + result.stdout
    log_text = "\n".join(path.read_text(encoding="utf-8") for path in (repo / "logs").glob("*.log"))
    assert PING_URL not in log_text
    assert "Healthcheck ping (start) attempted" in log_text
    assert "Healthcheck ping (success) attempted" in log_text
    calls = (tmp_path / "curl.log").read_text(encoding="utf-8")
    assert f"{PING_URL}/start" in calls
    assert f"{PING_URL}/fail" not in calls
    assert PING_URL in calls


def test_hc_fail_ping_without_python_does_not_send_the_log(tmp_path: Path):
    curl_log = tmp_path / "curl.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_bin = bin_dir / "curl"
    curl_bin.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            printf 'ARGS:%s\\n' "$*" >> "{curl_log}"
            case "$*" in
              *--data-binary*) cat >> "{curl_log}" ;;
            esac
            exit 0
            """
        ),
        encoding="utf-8",
    )
    curl_bin.chmod(0o755)
    python_bin = bin_dir / "python3"
    python_bin.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    python_bin.chmod(0o755)
    job_log = tmp_path / "job.log"
    job_log.write_text("token=sekrit /home/ubuntu/turgot\n", encoding="utf-8")
    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        export PATH="{bin_dir}:/usr/bin:/bin"
        # shellcheck disable=SC1091
        source "{COMMON}"
        maintenance_hc_ping "{PING_URL}" fail "{job_log}"
        echo PING_OK
        """
    )
    result = _run(script)
    assert result.returncode == 0, result.stderr
    assert "PING_OK" in result.stdout
    calls = curl_log.read_text(encoding="utf-8")
    assert "job failed" in calls
    assert "sekrit" not in calls
    assert "/home/ubuntu" not in calls


def test_flock_job_failure_pings_fail_with_sanitized_line(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = _fake_tools(tmp_path)
    lock = tmp_path / "job.lock"
    script = textwrap.dedent(
        f"""\
        set -euo pipefail
        export PATH="{bin_dir}:$PATH"
        export REPO="{repo}"
        export HC_BOFIP_URL="{PING_URL}"
        export HC_SERVICE_PUBLIC_URL=""
        export HC_BACKUP_URL=""
        export HC_VERIFY_URL=""
        # shellcheck disable=SC1091
        source "{COMMON}"
        run_bad_job() {{
          echo "token=sekrit in the middle of the log"
          echo "ERROR: embed refused"
          return 3
        }}
        maintenance_with_flock bofip_update "{lock}" run_bad_job
        """
    )
    result = _run(script)
    assert result.returncode == 1
    calls = (tmp_path / "curl.log").read_text(encoding="utf-8")
    assert f"{PING_URL}/start" in calls
    assert f"{PING_URL}/fail" in calls
    assert "embed refused" in calls
    assert "sekrit" not in calls
    log_text = "\n".join(path.read_text(encoding="utf-8") for path in (repo / "logs").glob("*.log"))
    assert PING_URL not in log_text
    assert "sekrit" in log_text


def test_lock_held_does_not_ping(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    bin_dir = _fake_tools(tmp_path)
    lock = tmp_path / "job.lock"
    holder = subprocess.Popen(
        ["flock", "-n", str(lock), "sleep", "30"],
        stdin=subprocess.DEVNULL,
    )
    try:
        # Wait until the holder owns the lock.
        acquired = False
        for _ in range(50):
            probe = subprocess.run(
                ["flock", "-n", str(lock), "true"],
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if probe.returncode != 0:
                acquired = True
                break
        assert acquired, "failed to observe the held lock"
        script = textwrap.dedent(
            f"""\
            set -euo pipefail
            export PATH="{bin_dir}:$PATH"
            export REPO="{repo}"
            export HC_SERVICE_PUBLIC_URL="{PING_URL}"
            # shellcheck disable=SC1091
            source "{COMMON}"
            run_ok_job() {{ return 0; }}
            maintenance_with_flock db_update "{lock}" run_ok_job
            """
        )
        result = _run(script)
        assert result.returncode == 1, result.stderr
        assert not (tmp_path / "curl.log").exists()
        log_text = "\n".join(
            path.read_text(encoding="utf-8") for path in (repo / "logs").glob("*.log")
        )
        assert "Lock held" in log_text
        assert PING_URL not in log_text
    finally:
        holder.terminate()
        holder.wait(timeout=5)
