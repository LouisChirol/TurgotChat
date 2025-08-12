#!/usr/bin/env bash
set -euo pipefail

DIR="~/turgot/database"
PY="$DIR/.venv/bin/python"
SCRIPT="$DIR/database/run_update.py"
LOG_DIR="$DIR/logs"
LOCK_FILE="/tmp/turgot_update.lock"

mkdir -p "$LOG_DIR"
TS="$(date +%F_%H-%M-%S)"
LOGFILE="$LOG_DIR/update_$TS.log"

# Log everything to file
exec > >(tee -a "$LOGFILE") 2>&1

echo "==== TurgotChat DB update start: $TS ===="

# Ensure we run from repo root (so relative paths and .env are found)
cd "$DIR"

# Activate venv
source "$REPO/.venv/bin/activate"

# Load env (MISTRAL_API_KEY, etc.) if present
if [ -f "$REPO/.env" ]; then
  set -a
  source "$REPO/.env"
  set +a
fi

export PYTHONUNBUFFERED=1

# Prevent overlapping runs
flock -n "$LOCK_FILE" -c "$PY $SCRIPT --cleanup-old-dumps"

echo "==== ColbertChat DB update done: $(date +%F_%H-%M-%S) ===="