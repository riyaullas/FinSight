# Deploying FinSight with Docker Compose

## Services

| Service | Image | Purpose | Published ports |
|---|---|---|---|
| `proxy` | `caddy:2-alpine` | HTTPS; routes `/api/*` to the API and everything else to the UI | `HTTP_PORT` (80), `HTTPS_PORT` (443) |
| `frontend` | built from `frontend/` | Next.js web UI | none |
| `backend` | built from `backend/` | FastAPI; applies database migrations on start | none |
| `db` | `postgres:18-alpine` | PostgreSQL; data in the `db-data` volume | none |

The API and UI run as non-root users. The API runs with `ENVIRONMENT=production`, which hides the API docs
and enforces strong secrets, secure cookies and PostgreSQL.

## Configuration (`.env`)

`sh deploy/scripts/init-env.sh` creates `.env` with random secrets and refuses to overwrite an existing
file. `.env.example` lists every variable.

| Variable | Meaning |
|---|---|
| `SITE_ADDRESS` | Address Caddy serves, e.g. `finance.example.com`. `localhost` uses Caddy's local certificate. |
| `SITE_HOST` | Hostname only, checked by the API's allowed-hosts list. Usually the same as `SITE_ADDRESS`. |
| `HTTP_PORT`, `HTTPS_PORT` | Host ports to publish. |
| `POSTGRES_PASSWORD` | Database password (letters and digits only). |
| `SECRET_KEY` | Token signing key, at least 48 random characters. Changing it signs everyone out. |
| `FIELD_ENCRYPTION_KEY` | Fernet key for encrypted fields. Never lose or change it, or encrypted data becomes unreadable. |

## Common tasks

```bash
docker compose up -d --build      # start or upgrade; migrations run automatically
docker compose ps                 # health of each service
docker compose logs -f backend    # follow API logs
docker compose down               # stop; data stays in the volumes
```

## Backups

```bash
sh deploy/scripts/backup.sh
sh deploy/scripts/restore.sh backups/finsight-<timestamp>.sql.gz
```

`backup.sh` writes `backups/finsight-<UTC timestamp>.sql.gz`. `restore.sh` replaces all current data and
asks you to type `RESTORE` first. Copy `backups/` and `.env` to storage outside this machine: a backup is
only usable with the matching `FIELD_ENCRYPTION_KEY`.

## Demo data (optional)

```bash
docker compose exec backend python -m app.scripts.seed_demo --email demo@example.com
```

The demo company is separate from your real company, and every screen in it is labelled as synthetic data.
