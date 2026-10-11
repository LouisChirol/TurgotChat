#!/usr/bin/env bash
set -euo pipefail

# Weekly Service-Public download + delta embed.
REPO="${REPO:-/home/ubuntu/turgot}"
LOCK_FILE="/tmp/turgot_db_update.lock"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance_common.sh
source "$SCRIPT_DIR/maintenance_common.sh"

run_sp_job() {
  set +e
  local exit_code=0

  maintenance_preflight || return 1
  maintenance_backup_chroma

  docker compose --profile maintenance build db_updater || return $?
  maintenance_stop_backend

  docker compose --profile maintenance run --rm db_updater || exit_code=$?
  if [ "$exit_code" -eq 0 ]; then
    echo "Running retrieval evaluation set..."
    docker compose run --rm backend python scripts/run_retrieval_eval.py || exit_code=$?
  else
    echo "Skipping retrieval eval because db_updater failed (exit $exit_code)"
  fi

  maintenance_start_backend || exit_code=$?
  maintenance_recover_backend || exit_code=$?
  return "$exit_code"
}

maintenance_with_flock "db_update" "$LOCK_FILE" run_sp_job
