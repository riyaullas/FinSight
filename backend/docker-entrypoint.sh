#!/bin/sh
set -eu

# Apply database migrations before starting the API (set RUN_MIGRATIONS=false to skip).
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  alembic upgrade head
fi

exec "$@"
