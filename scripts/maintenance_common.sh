# Shared helpers for Service-Public and BOFiP maintenance crons.
# shellcheck shell=bash

MAINTENANCE_MIN_FREE_GB="${MAINTENANCE_MIN_FREE_GB:-15}"
MAINTENANCE_API_URL="${MAINTENANCE_API_URL:-https://turgot.louischirol.fr/api/}"
MAINTENANCE_BACKUP_KEEP="${MAINTENANCE_BACKUP_KEEP:-2}"
MAINTENANCE_BACKEND_WARMUP_SEC="${MAINTENANCE_BACKEND_WARMUP_SEC:-45}"

_MAINTENANCE_CHROMA_BACKUP=""

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
  cd "$repo"
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

maintenance_backup_chroma() {
  local repo backup_root ts dest
  repo="$(maintenance_repo)"
  backup_root="$repo/database/backups"
  mkdir -p "$backup_root"
  ts="$(date +%F_%H-%M-%S)"
  dest="$backup_root/chroma_${ts}"
  echo "Backing up chroma_db to ${dest}..."
  mkdir -p "$dest"
  rsync -a --delete "$repo/database/chroma_db/" "$dest/"
  _MAINTENANCE_CHROMA_BACKUP="$dest"
  maintenance_prune_old_backups "$backup_root"
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
  echo "Verifying Chroma..."
  docker compose run --rm --no-deps backend python scripts/verify_chroma.py
}

maintenance_verify_api() {
  echo "Verifying API at ${MAINTENANCE_API_URL}..."
  curl -fsS --max-time 120 "${MAINTENANCE_API_URL}" >/dev/null
}

maintenance_verify_stack() {
  maintenance_verify_chroma && maintenance_verify_api
}

maintenance_recover_backend() {
  local exit_code=0
  if ! maintenance_verify_stack; then
    echo "ERROR: post-maintenance verification failed; restoring chroma backup."
    maintenance_restore_chroma_backup || exit_code=$?
    maintenance_start_backend || exit_code=$?
    if maintenance_verify_stack; then
      echo "Recovered using chroma backup; investigate failed maintenance run."
      return 1
    fi
    echo "CRITICAL: backend unhealthy after chroma restore."
    return 1
  fi
  return 0
}

# flock wrapper: runs job function name passed as $3 inside lock.
maintenance_with_flock() {
  local job_name="$1"
  local lock_file="$2"
  local job_fn="$3"
  local repo
  repo="$(maintenance_repo)"

  maintenance_log_setup "$job_name"
  maintenance_load_env

  local flock_cmd
  flock_cmd="set +e
REPO='${repo}'
_MAINTENANCE_CHROMA_BACKUP=''
MAINTENANCE_MIN_FREE_GB='${MAINTENANCE_MIN_FREE_GB}'
MAINTENANCE_API_URL='${MAINTENANCE_API_URL}'
MAINTENANCE_BACKUP_KEEP='${MAINTENANCE_BACKUP_KEEP}'
MAINTENANCE_BACKEND_WARMUP_SEC='${MAINTENANCE_BACKEND_WARMUP_SEC}'
cd \"\${REPO}\"
if [ -f \"\${REPO}/.env\" ]; then set -a; source \"\${REPO}/.env\"; set +a; fi
$(declare -f maintenance_preflight maintenance_backup_chroma maintenance_stop_backend \
  maintenance_start_backend maintenance_verify_stack maintenance_recover_backend \
  maintenance_docker_prune maintenance_repo maintenance_disk_avail_gb \
  maintenance_restore_chroma_backup maintenance_prune_old_backups \
  maintenance_verify_chroma maintenance_verify_api)
$(declare -f "$job_fn")
$job_fn"

  if flock -n "$lock_file" bash -c "$flock_cmd"; then
    echo "==== ${job_name} done: $(date +%F_%H-%M-%S) ===="
    return 0
  fi

  echo "==== ${job_name} failed or lock held: $(date +%F_%H-%M-%S) ===="
  cd "$repo"
  docker compose up -d backend || true
  return 1
}
