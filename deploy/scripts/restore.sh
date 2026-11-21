#!/bin/sh
# Restore a backup made by backup.sh. This REPLACES the current database contents.
set -eu
cd "$(dirname "$0")/../.."

if [ $# -ne 1 ] || [ ! -f "$1" ]; then
  echo "Usage: $0 backups/finsight-<timestamp>.sql.gz" >&2
  exit 1
fi
printf "This replaces all data in the FinSight database with %s. Type RESTORE to continue: " "$1"
read -r answer
[ "$answer" = "RESTORE" ] || { echo "Cancelled."; exit 1; }

docker compose stop backend frontend
gunzip -c "$1" | docker compose exec -T db psql -U finsight -d finsight -v ON_ERROR_STOP=1 -q
docker compose start backend frontend
echo "Restore complete."
