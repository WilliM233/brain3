#!/bin/bash
set -euo pipefail

# -----------------------------------------------------------------------
# BRAIN 3.0 — PostgreSQL Backup Script
# Designed for TrueNAS cron: 0 2 * * * /path/to/scripts/backup.sh
# -----------------------------------------------------------------------

# Load .env defaults if available (run from project root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# shellcheck disable=SC1091
. "$PROJECT_DIR/.env" 2>/dev/null || true

# Configuration (override via environment or .env)
BACKUP_PATH="${BACKUP_PATH:-/mnt/pool/backups/brain3}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
CONTAINER_NAME="${DB_CONTAINER_NAME:-brain3-db}"
DB_USER="${POSTGRES_USER:-brain3}"
DB_NAME="${POSTGRES_DB:-brain3}"
LOG_FILE="$BACKUP_PATH/backup.log"

# Timestamp for this run
TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
FILENAME="brain3_${TIMESTAMP}.sql.gz"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Ensure backup directory exists
mkdir -p "$BACKUP_PATH"

# Trap errors
trap 'log "FAIL: Backup failed with exit code $?"; exit 1' ERR

# Run backup
log "Starting backup: $FILENAME"
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_PATH/$FILENAME"

# Verify the file exists and is non-empty
if [ ! -s "$BACKUP_PATH/$FILENAME" ]; then
    log "FAIL: Backup file is empty or missing"
    exit 1
fi

FILE_SIZE="$(du -h "$BACKUP_PATH/$FILENAME" | cut -f1)"
log "OK: Backup complete — $FILENAME ($FILE_SIZE)"

# Clean up old backups
DELETED=$(find "$BACKUP_PATH" -name "brain3_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    log "Cleaned up $DELETED backup(s) older than $RETENTION_DAYS days"
fi

exit 0
