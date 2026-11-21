#!/bin/sh
# Create the root .env for docker compose with freshly generated secrets.
set -eu
cd "$(dirname "$0")/../.."

if [ -e .env ]; then
  echo ".env already exists; leaving it unchanged." >&2
  exit 1
fi

umask 077
cat > .env <<ENV
SITE_ADDRESS=${SITE_ADDRESS:-localhost}
SITE_HOST=${SITE_HOST:-localhost}
HTTP_PORT=80
HTTPS_PORT=443
POSTGRES_PASSWORD=$(openssl rand -hex 24)
SECRET_KEY=$(openssl rand -hex 48)
FIELD_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
ENV
echo "Wrote .env. Keep it private and back it up: without FIELD_ENCRYPTION_KEY, encrypted fields cannot be read."
