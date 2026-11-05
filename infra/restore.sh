#!/bin/sh
# Restore a backup made by infra/backup.sh. REPLACES the current data.
#
#   infra/restore.sh backups/2026-11-03_0200          # asks for confirmation
#   infra/restore.sh backups/2026-11-03_0200 --yes
#
# The stack must be running (docker compose … up -d). Databases are restored
# in place, uploads are replaced, then the services restart and the search
# index is rebuilt from the restored data.
set -eu
cd "$(dirname "$0")/.."
SRC=${1:?Usage: infra/restore.sh <backup folder> [--yes]}
COMPOSE=${COMPOSE:-"docker compose -f infra/docker-compose.yml --env-file .env"}
[ -f "$SRC/SHA256SUMS" ] || { echo "$SRC doesn't look like a backup folder"; exit 1; }
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) || { echo "checksums don't match: the backup is damaged"; exit 1; }
if [ "${2:-}" != "--yes" ]; then
  printf "This replaces ALL current website data with the backup in %s. Type RESTORE to continue: " "$SRC"
  read -r answer
  [ "$answer" = "RESTORE" ] || { echo "Cancelled."; exit 1; }
fi

for dump in "$SRC"/*.dump; do
  db=$(basename "$dump" .dump)
  # --clean --if-exists drops what's there first; ownership stays with each service's login
  $COMPOSE exec -T postgres pg_restore -U postgres --clean --if-exists --dbname "$db" < "$dump"
  echo "database $db restored"
done
$COMPOSE exec -T content-service sh -c 'find /srv/media -mindepth 1 -delete && tar xzf - -C /srv/media' < "$SRC/media.tar.gz"
echo "media restored"
$COMPOSE exec -T admission-service sh -c 'find /srv/private -mindepth 1 -delete && tar xzf - -C /srv/private' < "$SRC/private.tar.gz"
echo "private documents restored"

# restart so services drop cached connections; the search worker rebuilds the index on start
$COMPOSE restart
echo "restore complete"
