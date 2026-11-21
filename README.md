# FinSight

**One company. One system. Complete business visibility.**

FinSight is a self-hosted business finance platform: dashboards, payments, accounting, CRM, risk and
analytics for a single company, running on your own infrastructure. Financial data never leaves your
network, and no third-party AI or analytics services are used.

> **Status: Phase 1 (foundation), version 0.1.0.** Sign-in, security, company setup, onboarding, user
> and role management, the audit trail and the Overview dashboard work. The other modules are listed in
> the menu and clearly marked "Soon".

## What works today

| Area | Details |
|---|---|
| Sign-in and security | Argon2 password hashing, lockout after 5 failed attempts, TOTP two-factor authentication with one-time recovery codes (secret encrypted at rest), CSRF protection, refresh-token rotation with reuse detection, sign-out of other devices on password change |
| Access control | 7 built-in roles (Owner, Administrator, Finance Manager, Accountant, Sales & CRM, Shareholder (read-only), Employee) plus custom roles; users cannot grant permissions they do not hold; all data is scoped to the company |
| Audit trail | Hash-chained, tamper-evident log of security and administrative actions |
| Overview dashboard | 12 KPIs (revenue, expenses, net and gross profit, cash, runway, MRR, receivables, payables, customers, sales, overdue invoices), 6 charts, recent transactions, alerts and a rule-based business summary, all computed from the database |
| Setup | First-run company creation, 3-step onboarding, settings for company, users, roles, security and audit log; light and dark themes |
| Demo data | Optional separate company filled with clearly labelled synthetic data |

## Architecture

```
            +------------- Docker network (private) -------------+
 Browser -->| Caddy (HTTPS) --/api/*--> FastAPI --> PostgreSQL    |
            |               +--other--> Next.js UI                |
            +-----------------------------------------------------+
```

- `backend/`: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (SQLite for local development)
- `frontend/`: Next.js 16, React 19, TypeScript, Tailwind CSS
- `deploy/`: Caddy configuration and scripts for secrets, backup and restore
- `.github/workflows/ci.yml`: lint, tests on SQLite and PostgreSQL, migration checks, frontend build, dependency audits and a Docker smoke test

## Run with Docker (recommended)

Requirements: Docker Engine or Docker Desktop with Compose v2, plus `sh` and `openssl` (Git Bash works on Windows).

```bash
sh deploy/scripts/init-env.sh
docker compose up -d --build
```

Open <https://localhost>. The first visit leads to company setup, where you create the Owner account.
With `SITE_ADDRESS=localhost`, Caddy uses its own local certificate, so the browser warns until you trust
it. Set `SITE_ADDRESS` and `SITE_HOST` in `.env` to a real domain name to get a trusted certificate
automatically.

See [docs/deployment.md](docs/deployment.md) for configuration, upgrades, backups and restore.

## Local development

Requirements: Python 3.12+ and Node.js 20.9+.

Backend (http://127.0.0.1:8000, SQLite by default):

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
cp .env.example .env                                # then fill in SECRET_KEY and FIELD_ENCRYPTION_KEY
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Frontend (http://localhost:3000, proxies `/api` to the backend):

```bash
cd frontend
npm ci
npm run dev
```

Demo data (optional, creates a separate labelled company; asks for a password or reads `DEMO_PASSWORD`):

```bash
cd backend
.venv/Scripts/python -m app.scripts.seed_demo --email demo@example.com
```

## Checks

```bash
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/pytest
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

To run the backend tests against PostgreSQL, set `TEST_DATABASE_URL`, for example
`postgresql+psycopg://user:password@localhost:5432/finsight_test`. The tests wipe that database.

## Security

- Secrets come only from environment variables or a git-ignored `.env`. In production the API refuses to
  start with a weak `SECRET_KEY`, without `FIELD_ENCRYPTION_KEY`, without secure cookies, or on SQLite.
- Back up `.env` together with the database: without `FIELD_ENCRYPTION_KEY`, encrypted fields such as
  two-factor secrets cannot be read.
- Please report vulnerabilities privately to the maintainers, not in a public issue.

## Roadmap

Finance, Payments (gateway connections and bank imports), Accounting, Fraud & Risk, CRM, Sales,
Customers, Employees, Vendors, Analytics, Reports, Notifications and a local AI assistant.
See [CHANGELOG.md](CHANGELOG.md) for released changes.
