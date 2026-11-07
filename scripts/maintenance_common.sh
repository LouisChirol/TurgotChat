# Shared helpers for Service-Public and BOFiP maintenance crons.
# shellcheck shell=bash
#
# Optional healthchecks.io-style ping URLs (unset = skip silently):
#   HC_SERVICE_PUBLIC_URL  weekly Service-Public job
#   HC_BOFIP_URL           monthly BOFiP job
#   HC_BACKUP_URL          chroma snapshot step
#   HC_VERIFY_URL          post-update verify/recover step
# Each value is the check's base ping URL, without /start or /fail.

MAINTENANCE_MIN_FREE_GB="${MAINTENANCE_MIN_FREE_GB:-15}"
MAINTENANCE_API_URL="${MAINTENANCE_API_URL:-https://turgot.louischirol.fr/api/}"
MAINTENANCE_BACKUP_KEEP="${MAINTENANCE_BACKUP_KEEP:-2}"
MAINTENANCE_BACKEND_WARMUP_SEC="${MAINTENANCE_BACKEND_WARMUP_SEC:-45}"

_MAINTENANCE_CHROMA_BACKUP=""
_MAINTENANCE_SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/maintenance_common.sh"

maintenance_repo() {
  echo "${REPO:-/home/ubuntu/turgot}"
}

maintenance_log_setup() {
  local job_name="$1"
  local log_dir
  log_dir="$(maintenance_repo)/logs"
  mkdir -p "$log_dir"
  local ts
  ts="$(date +%F_%H-%M-%S)"
  MAINTENANCE_LOGFILE="$log_dir/${job_name}_${ts}.log"
  exec >>"$MAINTENANCE_LOGFILE" 2>&1
  echo "==== ${job_name} start: ${ts} (log=${MAINTENANCE_LOGFILE}) ===="
}

maintenance_load_env() {
  local repo
  repo="$(maintenance_repo)"
  cd "$repo" || return 1
  if [ -f "$repo/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$repo/.env"
    set +a
  fi
}

maintenance_disk_avail_gb() {
  df -BG / | awk 'NR==2 { gsub(/G/,"",$4); print $4 }'
}

maintenance_preflight() {
  local avail_gb
  avail_gb="$(maintenance_disk_avail_gb)"
  echo "Disk free on /: ${avail_gb}G (minimum ${MAINTENANCE_MIN_FREE_GB}G)"
  if [ "${avail_gb}" -lt "${MAINTENANCE_MIN_FREE_GB}" ]; then
    echo "ERROR: insufficient disk space; aborting before stopping backend."
    return 1
  fi
  maintenance_docker_prune
  return 0
}

maintenance_docker_prune() {
  echo "Pruning unused Docker images and build cache (older than 7 days)..."
  docker image prune -f --filter "until=168h" || true
  docker builder prune -f --filter "until=168h" 2>/dev/null || true
}

maintenance_wait_for_dns() {
  local host="${1:-auth.docker.io}"
  local attempt
  for attempt in 1 2 3 4 5; do
    if getent hosts "$host" >/dev/null 2>&1; then
      return 0
    fi
    echo "DNS lookup for ${host} failed (attempt ${attempt}/5)..."
    resolvectl flush-caches 2>/dev/null || true
    sleep $((attempt * 5))
  done
  echo "ERROR: DNS still failing for ${host}"
  return 1
}

maintenance_ensure_db_updater_base_image() {
  local base_image="${MAINTENANCE_DB_UPDATER_BASE_IMAGE:-python:3.13-slim}"
  if docker image inspect "${base_image}" >/dev/null 2>&1; then
    echo "Base image ${base_image} already present locally."
    return 0
  fi
  echo "Base image ${base_image} missing; pulling with retries..."
  maintenance_wait_for_dns auth.docker.io || return 1
  local attempt
  for attempt in 1 2 3 4 5; do
    if docker pull "${base_image}"; then
      return 0
    fi
    echo "docker pull failed (attempt ${attempt}/5)..."
    maintenance_wait_for_dns registry-1.docker.io || true
    sleep $((attempt * 10))
  done
  return 1
}

maintenance_build_db_updater() {
  local repo
  repo="$(maintenance_repo)"
  maintenance_ensure_db_updater_base_image || return 1
  echo "Building db_updater image (pull=false, local base only)..."
  # compose v2.24 only supports boolean --pull; plain `docker build` avoids Hub metadata checks.
  docker build --pull=false -t turgot-db_updater -f "${repo}/database/Dockerfile" "${repo}/database"
}

maintenance_backup_chroma() {
  local repo backup_root ts dest rc start
  start="$(date +%s)"
  maintenance_hc_ping "$(maintenance_hc_url_for backup)" start || true

  repo="$(maintenance_repo)"
  backup_root="$repo/database/backups"
  mkdir -p "$backup_root"
  ts="$(date +%F_%H-%M-%S)"
  dest="$backup_root/chroma_${ts}"
  echo "Backing up chroma_db to ${dest}..."
  mkdir -p "$dest"
  rsync -a --delete "$repo/database/chroma_db/" "$dest/"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "ERROR: chroma backup rsync failed"
    rm -rf "$dest"
    maintenance_hc_ping "$(maintenance_hc_url_for backup)" fail "${MAINTENANCE_LOGFILE:-}" || true
    maintenance_record_status backup error "$(( $(date +%s) - start ))" "chroma backup rsync failed" 0 || true
    return "$rc"
  fi

  _MAINTENANCE_CHROMA_BACKUP="$dest"
  maintenance_prune_old_backups "$backup_root"
  maintenance_hc_ping "$(maintenance_hc_url_for backup)" success || true
  maintenance_record_status backup ok "$(( $(date +%s) - start ))" "" 0 || true
  return 0
}

maintenance_prune_old_backups() {
  local backup_root="$1"
  local keep="${MAINTENANCE_BACKUP_KEEP}"
  mapfile -t backups < <(find "$backup_root" -maxdepth 1 -type d -name 'chroma_*' | sort -r)
  local i
  for i in "${!backups[@]}"; do
    if [ "$i" -ge "$keep" ]; then
      echo "Removing old chroma backup: ${backups[$i]}"
      rm -rf "${backups[$i]}"
    fi
  done
}

maintenance_restore_chroma_backup() {
  local repo
  repo="$(maintenance_repo)"
  if [ -z "${_MAINTENANCE_CHROMA_BACKUP}" ] || [ ! -d "${_MAINTENANCE_CHROMA_BACKUP}" ]; then
    echo "ERROR: no chroma backup available to restore."
    return 1
  fi
  echo "Restoring chroma_db from ${_MAINTENANCE_CHROMA_BACKUP}..."
  maintenance_stop_backend
  rsync -a --delete "${_MAINTENANCE_CHROMA_BACKUP}/" "$repo/database/chroma_db/"
  return 0
}

maintenance_stop_backend() {
  echo "Stopping backend..."
  docker compose stop backend || true
  local i
  for i in $(seq 1 30); do
    if [ -z "$(docker compose ps -q backend)" ] || \
      [ "$(docker inspect -f '{{.State.Running}}' "$(docker compose ps -q backend)" 2>/dev/null || echo false)" = "false" ]; then
      return 0
    fi
    sleep 1
  done
  echo "WARNING: backend still running after 30s"
}

maintenance_start_backend() {
  echo "Starting backend..."
  docker compose up -d backend || return $?
  sleep "${MAINTENANCE_BACKEND_WARMUP_SEC}"
  return 0
}

maintenance_verify_chroma() {
  local repo
  repo="$(maintenance_repo)"
  echo "Verifying Chroma (db_updater image, same client as embed)..."
  # "OK: <collection> count=<n>" is parsed into status.json collection counts.
  docker run --rm \
    -v "${repo}/database/chroma_db:/app/database/chroma_db" \
    turgot-db_updater python -c "
from chromadb import PersistentClient
c = PersistentClient(path='/app/database/chroma_db')
for name in ('service_public', 'bofip'):
    n = c.get_collection(name).count()
    assert n > 0, f'{name} empty'
    print(f'OK: {name} count={n}')
"
}

maintenance_verify_api() {
  echo "Verifying API at ${MAINTENANCE_API_URL}..."
  curl -fsS --max-time 120 "${MAINTENANCE_API_URL}" >/dev/null
}

maintenance_verify_stack() {
  maintenance_verify_chroma && maintenance_verify_api
}

# After embed, before bringing API back: ensure Chroma opens with the updater client.
maintenance_verify_chroma_pre_backend() {
  maintenance_verify_chroma
}

maintenance_recover_backend() {
  local exit_code=0
  if maintenance_verify_api; then
    echo "API healthy after maintenance."
    return 0
  fi
  echo "ERROR: API unhealthy after maintenance; restoring chroma backup."
  maintenance_restore_chroma_backup || exit_code=$?
  maintenance_start_backend || exit_code=$?
  if maintenance_verify_api; then
    echo "Recovered using chroma backup; investigate failed maintenance run."
    return 1
  fi
  echo "CRITICAL: API still unhealthy after chroma restore."
  return 1
}

# Ping a healthchecks.io-style URL. Never fails the caller.
# event: start -> $URL/start, success -> $URL,
# fail -> $URL/fail with one sanitized line (not the raw log).
maintenance_hc_ping() {
  local url="${1:-}"
  local event="${2:-success}"
  local logfile="${3:-}"
  local target body

  if [ -z "$url" ]; then
    return 0
  fi
  if ! command -v curl >/dev/null 2>&1; then
    return 0
  fi

  target="${url%/}"
  case "$event" in
    start) target="${target}/start" ;;
    fail) target="${target}/fail" ;;
    success) ;;
    *) return 0 ;;
  esac

  if [ "$event" = "fail" ] && [ -n "$logfile" ] && [ -f "$logfile" ]; then
    body="$(maintenance_hc_fail_body "$logfile")"
    printf '%s' "$body" | curl \
      --silent --show-error \
      --max-time 10 --connect-timeout 5 \
      --retry 0 \
      --header "Content-Type: text/plain" \
      --data-binary @- \
      --output /dev/null \
      "$target" >/dev/null 2>&1 || true
  else
    curl \
      --silent --show-error \
      --max-time 10 --connect-timeout 5 \
      --retry 0 \
      --output /dev/null \
      "$target" >/dev/null 2>&1 || true
  fi
  echo "Healthcheck ping (${event}) attempted"
  return 0
}

maintenance_hc_url_for() {
  local url=""
  case "$1" in
    db_update | service_public) url="${HC_SERVICE_PUBLIC_URL:-}" ;;
    bofip_update | bofip) url="${HC_BOFIP_URL:-}" ;;
    backup) url="${HC_BACKUP_URL:-}" ;;
    verify) url="${HC_VERIFY_URL:-}" ;;
    *) url="" ;;
  esac
  printf '%s' "$url"
}

maintenance_status_job_name() {
  case "$1" in
    db_update | service_public) printf '%s' service_public ;;
    bofip_update | bofip) printf '%s' bofip ;;
    backup) printf '%s' backup ;;
    verify) printf '%s' verify ;;
    *) return 1 ;;
  esac
}

maintenance_status_py() {
  local candidate
  candidate="$(maintenance_repo)/backend/app/maintenance_status.py"
  if [ -f "$candidate" ]; then
    printf '%s' "$candidate"
    return 0
  fi
  # Cron tests and a partial checkout may not set REPO. The writer lives next
  # to this script in the git tree.
  candidate="$(cd "$(dirname "${_MAINTENANCE_SELF}")/.." && pwd)/backend/app/maintenance_status.py"
  printf '%s' "$candidate"
}

# One line safe to POST to healthchecks.io. Falls back to a fixed phrase so a
# missing interpreter cannot leak the raw log line.
maintenance_sanitize_for_ping() {
  local message="${1-}"
  local py clean
  if [ -z "$message" ]; then
    printf '%s' "job failed"
    return 0
  fi
  py="$(maintenance_status_py)"
  if [ -f "$py" ] && command -v python3 >/dev/null 2>&1; then
    clean="$(printf '%s' "$message" | python3 "$py" sanitize-error 2>/dev/null || true)"
    if [ -n "$clean" ]; then
      printf '%s' "$clean"
      return 0
    fi
  fi
  printf '%s' "job failed"
}

maintenance_hc_fail_body() {
  local line
  line="$(maintenance_short_error "${1:-}")"
  line="${line:0:4000}"
  maintenance_sanitize_for_ping "$line"
}

maintenance_status_file() {
  if [ -n "${MAINTENANCE_STATUS_PATH:-}" ]; then
    printf '%s' "$MAINTENANCE_STATUS_PATH"
    return 0
  fi
  printf '%s' "$(maintenance_repo)/backend/logs/maintenance_status.json"
}

maintenance_newest_backup_at() {
  local root py names
  root="$(maintenance_repo)/database/backups"
  py="$(maintenance_status_py)"
  if [ ! -d "$root" ] || [ ! -f "$py" ] || ! command -v python3 >/dev/null 2>&1; then
    return 0
  fi
  names="$(find "$root" -maxdepth 1 -mindepth 1 -type d -name 'chroma_*' -printf '%f\n' 2>/dev/null || true)"
  if [ -z "$names" ]; then
    return 0
  fi
  printf '%s\n' "$names" | python3 "$py" newest-backup 2>/dev/null || true
}

maintenance_collection_counts_via_docker() {
  local repo
  repo="$(maintenance_repo)"
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if ! docker image inspect turgot-db_updater >/dev/null 2>&1; then
    return 0
  fi
  if command -v timeout >/dev/null 2>&1; then
    timeout 45 docker run --rm \
      -v "${repo}/database/chroma_db:/app/database/chroma_db:ro" \
      turgot-db_updater python -c '
import json
from chromadb import PersistentClient
client = PersistentClient(path="/app/database/chroma_db")
counts = {}
for col in client.list_collections():
    name = col if isinstance(col, str) else getattr(col, "name", "")
    if isinstance(name, str) and name[:1].isalpha() and name.replace("_", "").isalnum():
        counts[name] = int(client.get_collection(name).count())
print(json.dumps(counts, sort_keys=True))
' 2>/dev/null || true
    return 0
  fi
  docker run --rm \
    -v "${repo}/database/chroma_db:/app/database/chroma_db:ro" \
    turgot-db_updater python -c '
import json
from chromadb import PersistentClient
client = PersistentClient(path="/app/database/chroma_db")
counts = {}
for col in client.list_collections():
    name = col if isinstance(col, str) else getattr(col, "name", "")
    if isinstance(name, str) and name[:1].isalpha() and name.replace("_", "").isalnum():
        counts[name] = int(client.get_collection(name).count())
print(json.dumps(counts, sort_keys=True))
' 2>/dev/null || true
}

maintenance_collection_counts_json() {
  local py logfile out
  py="$(maintenance_status_py)"
  logfile="${MAINTENANCE_LOGFILE:-}"
  if [ -n "$logfile" ] && [ -f "$logfile" ] && [ -f "$py" ] && command -v python3 >/dev/null 2>&1; then
    out="$(python3 "$py" counts-from-log --file "$logfile" 2>/dev/null || true)"
    if [ -n "$out" ] && [ "$out" != "{}" ]; then
      printf '%s' "$out"
      return 0
    fi
  fi
  maintenance_collection_counts_via_docker
}

# maintenance_record_status JOB STATUS DURATION_SECONDS [ERROR] [REFRESH_COUNTS]
# REFRESH_COUNTS=1 merges collection counts from the log, or from Chroma if the
# log has none. Failures are logged and ignored.
maintenance_record_status() {
  local job="$1"
  local status="$2"
  local duration="$3"
  local error="${4:-}"
  local refresh="${5:-0}"
  local py file backup_at counts
  py="$(maintenance_status_py)"
  file="$(maintenance_status_file)"

  if [ ! -f "$py" ] || ! command -v python3 >/dev/null 2>&1; then
    echo "WARNING: skipping maintenance status file (python3 or writer missing)"
    return 0
  fi

  mkdir -p "$(dirname "$file")" 2>/dev/null || true

  local -a cmd
  cmd=(python3 "$py" record --file "$file" --job "$job" --status "$status" --duration "$duration" --error "$error")

  backup_at="$(maintenance_newest_backup_at || true)"
  if [ -n "$backup_at" ]; then
    cmd+=(--newest-backup-at "$backup_at")
  fi

  if [ "$refresh" = "1" ]; then
    counts="$(maintenance_collection_counts_json || true)"
    if [ -n "$counts" ] && [ "$counts" != "{}" ]; then
      cmd+=(--collections "$counts")
    fi
  fi

  if ! "${cmd[@]}"; then
    echo "WARNING: failed to write maintenance status for ${job}"
  fi
  return 0
}

maintenance_short_error() {
  local logfile="${1:-}"
  local line=""
  if [ -n "$logfile" ] && [ -f "$logfile" ]; then
    line="$(awk 'NF && $0 !~ /^==== / && $0 !~ /^Healthcheck ping / { line=$0 } END { print line }' "$logfile" 2>/dev/null || true)"
  fi
  if [ -z "$line" ]; then
    line="job failed"
  fi
  printf '%s' "$line"
}

maintenance_finish_observed_job() {
  local cron_name="$1"
  local exit_code="$2"
  local started="$3"
  local error_override="${4:-}"
  local status_job duration url error

  status_job="$(maintenance_status_job_name "$cron_name")" || return 0
  duration="$(( $(date +%s) - started ))"
  if [ "$duration" -lt 0 ]; then
    duration=0
  fi
  url="$(maintenance_hc_url_for "$status_job")"

  if [ "$exit_code" -eq 0 ]; then
    maintenance_hc_ping "$url" success || true
    maintenance_record_status "$status_job" ok "$duration" "" 1 || true
    return 0
  fi

  if [ -n "$error_override" ]; then
    error="$error_override"
  else
    error="$(maintenance_short_error "${MAINTENANCE_LOGFILE:-}")"
  fi
  maintenance_hc_ping "$url" fail "${MAINTENANCE_LOGFILE:-}" || true
  maintenance_record_status "$status_job" error "$duration" "$error" 1 || true
  return 0
}

# Verify the public API (and restore the chroma snapshot on failure).
# Reports HC_VERIFY_URL independently of the parent job ping.
maintenance_verify_and_recover() {
  local start rc
  start="$(date +%s)"
  maintenance_hc_ping "$(maintenance_hc_url_for verify)" start || true
  rc=0
  maintenance_recover_backend || rc=$?
  if [ "$rc" -eq 0 ]; then
    maintenance_hc_ping "$(maintenance_hc_url_for verify)" success || true
    maintenance_record_status verify ok "$(( $(date +%s) - start ))" "" 0 || true
  else
    maintenance_hc_ping "$(maintenance_hc_url_for verify)" fail "${MAINTENANCE_LOGFILE:-}" || true
    maintenance_record_status verify error "$(( $(date +%s) - start ))" "post-update verify failed" 0 || true
  fi
  return "$rc"
}

# flock wrapper: runs job function name passed as $3 inside lock.
maintenance_with_flock() {
  local job_name="$1"
  local lock_file="$2"
  local job_fn="$3"
  local repo started result_file outcome code pre_error
  repo="$(maintenance_repo)"

  maintenance_log_setup "$job_name"
  maintenance_load_env
  export MAINTENANCE_LOGFILE
  export MAINTENANCE_MIN_FREE_GB MAINTENANCE_API_URL MAINTENANCE_BACKUP_KEEP
  export MAINTENANCE_BACKEND_WARMUP_SEC
  export HC_SERVICE_PUBLIC_URL="${HC_SERVICE_PUBLIC_URL:-}"
  export HC_BOFIP_URL="${HC_BOFIP_URL:-}"
  export HC_BACKUP_URL="${HC_BACKUP_URL:-}"
  export HC_VERIFY_URL="${HC_VERIFY_URL:-}"
  export MAINTENANCE_STATUS_PATH="${MAINTENANCE_STATUS_PATH:-}"

  started="$(date +%s)"
  result_file="$(mktemp)"

  local flock_cmd
  flock_cmd="set +e
export REPO='${repo}'
export MAINTENANCE_STATUS_PATH='${MAINTENANCE_STATUS_PATH:-}'
source '${_MAINTENANCE_SELF}' || exit 1
cd \"\$REPO\"
if [ -f \"\$REPO/.env\" ]; then set -a; . \"\$REPO/.env\"; set +a; fi
printf '%s\n' running > '${result_file}'
maintenance_hc_ping \"\$(maintenance_hc_url_for '${job_name}')\" start || true
$(declare -f "$job_fn")
${job_fn}
job_status=\$?
printf '%s\n' \"\$job_status\" > '${result_file}'
exit \$job_status"

  if flock -n "$lock_file" bash -c "$flock_cmd"; then
    echo "==== ${job_name} done: $(date +%F_%H-%M-%S) ===="
    maintenance_finish_observed_job "$job_name" 0 "$started" || true
    rm -f "$result_file"
    return 0
  fi

  outcome="$(tr -d '[:space:]' < "$result_file" 2>/dev/null || true)"
  rm -f "$result_file"

  if [ -z "$outcome" ]; then
    echo "==== ${job_name} failed or lock held: $(date +%F_%H-%M-%S) ===="
    echo "Lock held; not sending a failure ping."
    if cd "$repo"; then
      docker compose up -d backend || true
    fi
    return 1
  fi

  code=1
  case "$outcome" in
    "" | *[!0-9]*) code=1 ;;
    *) code="$outcome" ;;
  esac
  # Capture the job's own last line before recovery logs append to the file.
  # The status document keeps that line. The failure ping sends one sanitized
  # line from the log as it stands when the ping is built.
  pre_error="$(maintenance_short_error "${MAINTENANCE_LOGFILE:-}")"
  echo "==== ${job_name} failed or lock held: $(date +%F_%H-%M-%S) ===="
  if cd "$repo"; then
    docker compose up -d backend || true
  fi
  maintenance_finish_observed_job "$job_name" "$code" "$started" "$pre_error" || true
  return 1
}
