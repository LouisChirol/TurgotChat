#!/usr/bin/env bash
set -euo pipefail

DIR="~/turgot/database"
LOG_DIR="$DIR/logs"
LOCK_FILE="/tmp/turgot_db_update.lock"

mkdir -p "$LOG_DIR"
TS="$(date +%F_%H-%M-%S)"
LOGFILE="$LOG_DIR/db_update_$TS.log"

# Log everything
exec > >(tee -a "$LOGFILE") 2>&1

echo "==== DB updater start: $TS ===="
cd "$DIR"

# Ensure env for compose interpolation
if [ -f "$DIR/.env" ]; then
  set -a; source "$DIR/.env"; set +a
fi

# Prevent overlapping runs; run updater container once and remove it
flock -n "$LOCK_FILE" -c "docker compose run --rm db_updater"

echo '==== DB updater done: '$(date +%F_%H-%M-%S)