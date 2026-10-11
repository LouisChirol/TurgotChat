#!/usr/bin/env bash
set -euo pipefail

# Monthly BOFiP download + delta embed (content-hash tracking in bofip_tracking.sqlite3).
REPO="${REPO:-/home/ubuntu/turgot}"
LOCK_FILE="/tmp/turgot_bofip_update.lock"
export BOFIP_MAX_COST_USD="${BOFIP_MAX_COST_USD:-5.00}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=maintenance_common.sh
source "$SCRIPT_DIR/maintenance_common.sh"

run_bofip_job() {
  set +e
  local exit_code=0

  maintenance_preflight || return 1
  maintenance_backup_chroma

  docker compose --profile maintenance build db_updater || return $?
  maintenance_stop_backend

  docker compose --profile maintenance run --rm db_updater \
    python -m sources.bofip.run_update --max-cost-usd "${BOFIP_MAX_COST_USD}" || exit_code=$?

  maintenance_start_backend || exit_code=$?
  maintenance_recover_backend || exit_code=$?
  return "$exit_code"
}

maintenance_with_flock "bofip_update" "$LOCK_FILE" run_bofip_job
