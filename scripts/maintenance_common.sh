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
  local repo
  repo="$(maintenance_repo)"
  echo "Verifying Chroma (db_updater image, same client as embed)..."
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
  maintenance_verify_chroma maintenance_verify_api maintenance_build_db_updater \
  maintenance_ensure_db_updater_base_image maintenance_wait_for_dns \
  maintenance_verify_chroma_pre_backend maintenance_verify_stack)
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
