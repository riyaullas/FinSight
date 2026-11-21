# Changelog

All notable changes to FinSight are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Docker Compose stack: PostgreSQL 18, API, web UI and a Caddy HTTPS reverse proxy. Only the proxy
  publishes ports.
- Scripts to generate `.env` secrets and to back up and restore the database.
- GitHub Actions CI: backend lint and tests on SQLite and PostgreSQL, migration and schema-drift check,
  frontend typecheck, lint, tests and build, dependency audits, and a Docker Compose smoke test.
- Backend tests can target PostgreSQL through `TEST_DATABASE_URL`.

### Fixed
- Buttons that wrap a link crashed the dashboard's empty state.
- Rupee amounts in the business summary use Indian digit grouping (₹6,24,877.69).
- The cash runway tile no longer cuts off its label ("No net burn").

## [0.1.0] - Phase 1 foundation

### Added
- Company setup, onboarding, and settings for company profile, users, roles, security and audit log.
- Authentication with Argon2 password hashing, account lockout, TOTP two-factor authentication with
  recovery codes, CSRF protection and refresh-token rotation with reuse detection.
- Role-based access control with 7 built-in roles and custom roles, scoped per company.
- Hash-chained, tamper-evident audit log.
- Overview dashboard with 12 KPIs, 6 charts, recent transactions, alerts and a rule-based summary.
- Script to seed a synthetic demo company.
