#!/bin/sh
# Back up everything the NCIT website can't recreate by itself:
#   - every service database (PostgreSQL custom-format dumps)
#   - uploaded photos and PDFs (the "media" volume)
#   - private application documents and CVs (the "private" volume)
#
#   infra/backup.sh                 # writes backups/<date-time>/ and keeps 14 days
#   BACKUP_DIR=/mnt/nas KEEP_DAYS=30 infra/backup.sh
#   COMPOSE="docker compose -f infra/docker-compose.yml -f infra/docker-compose.tls.yml --env-file .env" infra/backup.sh
#
# Copy the result OFF the server as well (another machine, a NAS or cloud storage):
# a backup on the same disk doesn't survive the disk failing.
# Not backed up on purpose: Redis (sign-in sessions and queues; people just sign in again)
# and the search index (rebuilt automatically from the other databases).
set -eu
cd "$(dirname "$0")/.."
COMPOSE=${COMPOSE:-"docker compose -f infra/docker-compose.yml --env-file .env"}
DBS="ncit_auth ncit_audit ncit_academics ncit_content ncit_events ncit_eca ncit_notify ncit_admissions ncit_careers ncit_alumni"
BACKUP_DIR=${BACKUP_DIR:-backups}
KEEP_DAYS=${KEEP_DAYS:-14}
STAMP=$(date +%Y-%m-%d_%H%M)
OUT="$BACKUP_DIR/$STAMP"
mkdir -p "$OUT"
chmod 700 "$OUT"   # contains personal data: applicants' details and documents

for db in $DBS; do
  $COMPOSE exec -T postgres pg_dump -U postgres --format=custom "$db" > "$OUT/$db.dump"
  echo "database $db: $(du -h "$OUT/$db.dump" | cut -f1)"
done
$COMPOSE exec -T content-service tar czf - -C /srv/media . > "$OUT/media.tar.gz"
echo "media: $(du -h "$OUT/media.tar.gz" | cut -f1)"
$COMPOSE exec -T admission-service tar czf - -C /srv/private . > "$OUT/private.tar.gz"
echo "private documents: $(du -h "$OUT/private.tar.gz" | cut -f1)"

(cd "$OUT" && sha256sum ./* > SHA256SUMS)
echo "backup written to $OUT"

# keep the last KEEP_DAYS days
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$KEEP_DAYS" -exec rm -rf {} +
