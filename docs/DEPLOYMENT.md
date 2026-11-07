# Deployment

This repository deploys backend updates through `.github/workflows/deploy.yml`.

## CI/CD flow

On every push to `master` (or manual `workflow_dispatch`):

1. Lint backend (`ruff`) and frontend (`npm run lint`)
2. Run backend tests (`pytest`) and Playwright happy-path e2e
3. Build and push backend image to GHCR (`ghcr.io/louischirol/turgotchat-backend:<sha>`)
4. SSH to the server, update `BACKEND_IMAGE`, restart backend, health-check `/`
5. On failure, rollback to the previous container image automatically

## Required GitHub secrets

- `DEPLOY_HOST`: server hostname or IP
- `DEPLOY_USER`: SSH user (e.g. `ubuntu`)
- `DEPLOY_PATH`: deployed repo path on server (e.g. `/home/ubuntu/turgot`)
- `DEPLOY_SSH_PRIVATE_KEY`: private key for SSH deploy user
- `GHCR_USERNAME`: GitHub username for pulling images on the server (if registry login required)
- `GHCR_TOKEN`: token with `read:packages` (if registry login required)

`GITHUB_TOKEN` is used automatically for GHCR push during CI.

## Server expectations

- Docker and Docker Compose installed
- External Docker network `web` (shared with Caddy in `~/lchirol/infra`)
- Repository at `DEPLOY_PATH` with `docker-compose.yml` and `.env`
- `.env` contains runtime secrets (`MISTRAL_API_KEY`, `REDIS_PASSWORD`, etc.)
- Caddy routes `turgot.louischirol.fr` → `turgot-frontend:3000`, `/api/*` → `turgot-backend:8000`
- Frontend build uses `NEXT_PUBLIC_API_URL=/api` (same-origin, no `api.turgotchat.fr` subdomain)
- `turgotchat.fr` redirects to `turgot.louischirol.fr`; `api.turgotchat.fr` kept as legacy API host
- Nginx on the host is **not** the edge proxy (Caddy binds 80/443)

## Manual deploy (without CI)

```bash
./scripts/copy_to_server.sh

# Sync vector DB (large; stop containers first)
ssh -i ~/.ssh/id_ed25519_colbert ubuntu@145.239.71.174 'cd ~/turgot && docker compose down'
rsync -avz --delete -e "ssh -i ~/.ssh/id_ed25519_colbert" \
  database/chroma_db/ ubuntu@145.239.71.174:~/turgot/database/chroma_db/

ssh -i ~/.ssh/id_ed25519_colbert ubuntu@145.239.71.174
cd ~/turgot && ./scripts/deploy.sh
```

Verify: `https://turgot.louischirol.fr` and `https://turgot.louischirol.fr/api/`

## Scheduled database updates (production server)

| Job | Schedule | Script | What it does |
|-----|----------|--------|----------------|
| Service-Public | Mon 03:00 | `scripts/cron_update_docker.sh` | Download SP XML, delta embed `service_public`, retrieval eval |
| BOFiP | 1st of month 04:00 | `scripts/cron_bofip_update_docker.sh` | Download BOFiP API, delta embed `bofip` (hash tracking) |

BOFiP cron uses `BOFIP_MAX_COST_USD` (default `5.00`) against **delta** embed estimate only. Logs: `~/turgot/logs/bofip_update_*.log` and `db_update_*.log`.

Both crons use `scripts/maintenance_common.sh`:

1. **Preflight** — abort (backend stays up) if free disk on `/` is below `MAINTENANCE_MIN_FREE_GB` (default `15`), then prune Docker images/build cache older than 7 days.
2. **Backup** — `rsync` of `database/chroma_db/` to `database/backups/chroma_<timestamp>/` (keep last 2).
3. Run `db_updater` with backend stopped.
4. **Verify** — `backend/scripts/verify_chroma.py` and `curl` to `MAINTENANCE_API_URL` (default `https://turgot.louischirol.fr/api/`).
5. On verify failure — restore the backup snapshot and restart backend.

`database/.dockerignore` keeps `chroma_db/` and `data/` out of the `db_updater` image build context.

`db_updater` builds use `docker build --pull=false` after ensuring `python:3.13-slim` exists locally (pull only when missing, with DNS retries). This avoids Monday 03:00 failures when `auth.docker.io` lookups flap on the host resolver.

Manual BOFiP run on server:

```bash
cd ~/turgot
BOFIP_MAX_COST_USD=5.00 ./scripts/cron_bofip_update_docker.sh
```

## Monitoring crons without SSH

Maintenance jobs can ping [healthchecks.io](https://healthchecks.io)-style URLs and publish a small status document. Both are optional: if the ping URLs are unset, the jobs behave as before.

### Ping URLs

Add these to `~/turgot/.env` (the cron `source`s that file). Use each check's base ping URL, with no `/start` or `/fail` suffix. Leave a variable unset to skip that ping. A ping uses a 10s timeout and cannot fail the job.

```bash
HC_SERVICE_PUBLIC_URL=https://hc-ping.com/<service-public-uuid>
HC_BOFIP_URL=https://hc-ping.com/<bofip-uuid>
HC_BACKUP_URL=https://hc-ping.com/<backup-uuid>
HC_VERIFY_URL=https://hc-ping.com/<verify-uuid>
```

| Env var | When it pings | Healthchecks period | Grace |
|---------|---------------|---------------------|-------|
| `HC_SERVICE_PUBLIC_URL` | `scripts/cron_update_docker.sh` (Mon 03:00) | 7 days | 1 day |
| `HC_BOFIP_URL` | `scripts/cron_bofip_update_docker.sh` (1st of the month, 04:00) | 31 days | 2 days |
| `HC_BACKUP_URL` | Chroma snapshot at the start of each of those jobs (at least weekly, again on the monthly run) | 7 days | 1 day |
| `HC_VERIFY_URL` | API verify/restore at the end of each of those jobs | 7 days | 1 day |

The host crontab's timezone is the clock those schedules use. Pings are `$URL/start` when the step starts, `$URL` on success, and `$URL/fail` on failure. The failure request body is one short line from that run's log, passed through the same `sanitize_error` filter as the public status file (paths, addresses, and secret-like tokens removed). The rest of the log stays on the server.

Create the checks:

1. Sign in at [healthchecks.io](https://healthchecks.io) and choose **Add Check**.
2. Name them after the four rows above. Schedule type **Simple**.
3. Set **Period** and **Grace** from the table (weekly jobs: period 7 days, grace 1 day; monthly BOFiP: period 31 days, grace 2 days).
4. Save, and copy the **Ping URL** into the matching variable in `~/turgot/.env`. Do not commit that file.
5. A new check expects a ping within period + grace. After creating one, send a single success ping so it does not alert before the next real run: `curl -fsS --max-time 10 "$HC_SERVICE_PUBLIC_URL"` (and the same for the other three).

### Status file and public endpoint

At the end of each job the cron updates `backend/logs/maintenance_status.json` (override with `MAINTENANCE_STATUS_PATH`). The existing backend mount `./backend/logs:/app/logs` makes that file visible in the container. No compose change is required. The host needs `python3` (stdlib only) so the cron can update the file; a writer failure is logged and does not fail the job.

`GET /api/health/data` (backend route `GET /health/data`) returns that document. Timestamps are UTC. Each job has `last_run_at`, `last_success_at`, `status` (`ok`, `error`, or `unknown`), `duration_seconds`, and a short `error`. The document also has `newest_backup_at` and `collections` (document counts). Paths, internal hostnames, addresses, and secret-like tokens are stripped. The response does not include the status file path. The route is limited to 30 requests per minute per visitor, using the `X-Real-IP` set by Caddy.

`GET /api/` and `GET /api/health` read the Chroma collection the process already has open. When that read works, `/api/` is still exactly `{"message":"Turgot API is running"}`. When it does not, both routes return HTTP 503 with `{"detail":"Chroma unavailable"}`. The deploy workflow's `curl` of `/` and the maintenance API check use that status code.

### Deploying this

1. Create the four healthchecks.io checks and set the env vars on the VPS (above).
2. Merge PR **#18** (`feat/maintenance-hardening`) into `master`, then merge the observability PR that stacks on it.
3. The push to `master` publishes the backend image and restarts it (this adds `/api/health` and `/api/health/data`).
4. On the VPS, `cd ~/turgot && git pull` so `scripts/maintenance_common.sh`, the cron entrypoints, and `backend/app/maintenance_status.py` match that image. Cron reads the scripts from the repo checkout, not from the image.
5. Check from outside: `https://turgot.louischirol.fr/api/` (same running message when Chroma answers), `https://turgot.louischirol.fr/api/health`, and `https://turgot.louischirol.fr/api/health/data`.

## Manual rollback

```bash
cd ~/turgot
# set BACKEND_IMAGE to previous tag in .env.deploy or .env
docker compose --env-file .env --env-file .env.deploy up -d backend
```

## Local testing before deploy

```bash
# Backend tests
cd backend && uv run pytest -q

# Full stack locally
docker compose up --build
# Frontend: http://localhost:3000  Backend: http://localhost:8000
```

See `database/README.md` for vector DB update workflows.
