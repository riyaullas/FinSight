#!/bin/sh
# Dump the PostgreSQL database to backups/ (compressed, readable only by you).
set -eu
cd "$(dirname "$0")/../.."

mkdir -p backups
umask 077
file="backups/finsight-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db pg_dump -U finsight -d finsight --no-owner --clean --if-exists | gzip > "$file"
echo "Backup written to $file"
