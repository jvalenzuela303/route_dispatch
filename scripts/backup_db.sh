#!/bin/bash
#
# Automated Database Backup Script
# Claude Logistics API - PostgreSQL + PostGIS
#
# Usage: ./scripts/backup_db.sh [--full|--schema-only|--data-only]
#

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# ============================================
# Configuration
# ============================================
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DATE_ONLY=$(date +"%Y%m%d")

# Database configuration
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="route_dispatch"
DB_USER="${DB_USER:-claude_admin}"

# Backup type (default: full)
BACKUP_TYPE="${1:---full}"

# ============================================
# Color output
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================
# Pre-flight checks
# ============================================
log_info "Starting backup at $(date)"

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    log_info "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Check if pg_dump is available
if ! command -v pg_dump &> /dev/null; then
    log_error "pg_dump not found. Please install postgresql-client."
    exit 1
fi

# Check if database is reachable
if ! PGPASSWORD=$DB_PASSWORD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME > /dev/null 2>&1; then
    log_error "Database is not reachable at $DB_HOST:$DB_PORT"
    exit 1
fi

# ============================================
# Perform Backup
# ============================================
case "$BACKUP_TYPE" in
    --full)
        BACKUP_FILE="$BACKUP_DIR/route_dispatch_full_$TIMESTAMP.sql.gz"
        log_info "Creating FULL backup: $BACKUP_FILE"

        PGPASSWORD=$DB_PASSWORD pg_dump \
            -h $DB_HOST \
            -p $DB_PORT \
            -U $DB_USER \
            -d $DB_NAME \
            --format=custom \
            --verbose \
            --clean \
            --if-exists \
            --create \
            --encoding=UTF8 \
            | gzip > "$BACKUP_FILE"
        ;;

    --schema-only)
        BACKUP_FILE="$BACKUP_DIR/route_dispatch_schema_$TIMESTAMP.sql.gz"
        log_info "Creating SCHEMA-ONLY backup: $BACKUP_FILE"

        PGPASSWORD=$DB_PASSWORD pg_dump \
            -h $DB_HOST \
            -p $DB_PORT \
            -U $DB_USER \
            -d $DB_NAME \
            --format=custom \
            --schema-only \
            --verbose \
            --encoding=UTF8 \
            | gzip > "$BACKUP_FILE"
        ;;

    --data-only)
        BACKUP_FILE="$BACKUP_DIR/route_dispatch_data_$TIMESTAMP.sql.gz"
        log_info "Creating DATA-ONLY backup: $BACKUP_FILE"

        PGPASSWORD=$DB_PASSWORD pg_dump \
            -h $DB_HOST \
            -p $DB_PORT \
            -U $DB_USER \
            -d $DB_NAME \
            --format=custom \
            --data-only \
            --verbose \
            --encoding=UTF8 \
            | gzip > "$BACKUP_FILE"
        ;;

    *)
        log_error "Invalid backup type: $BACKUP_TYPE"
        echo "Usage: $0 [--full|--schema-only|--data-only]"
        exit 1
        ;;
esac

# ============================================
# Verify Backup
# ============================================
if [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Backup completed successfully!"
    log_info "File: $BACKUP_FILE"
    log_info "Size: $BACKUP_SIZE"

    # Create symlink to latest backup
    LATEST_LINK="$BACKUP_DIR/route_dispatch_latest.sql.gz"
    ln -sf "$BACKUP_FILE" "$LATEST_LINK"
    log_info "Latest backup symlink updated: $LATEST_LINK"
else
    log_error "Backup file not created!"
    exit 1
fi

# ============================================
# Cleanup Old Backups
# ============================================
log_info "Cleaning up backups older than $RETENTION_DAYS days..."

DELETED_COUNT=0
while IFS= read -r -d '' old_backup; do
    log_warn "Deleting old backup: $(basename "$old_backup")"
    rm -f "$old_backup"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "route_dispatch_*.sql.gz" -type f -mtime +$RETENTION_DAYS -print0)

if [ $DELETED_COUNT -eq 0 ]; then
    log_info "No old backups to delete"
else
    log_info "Deleted $DELETED_COUNT old backup(s)"
fi

# ============================================
# Summary
# ============================================
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -name "route_dispatch_*.sql.gz" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo ""
log_info "==================================="
log_info "Backup Summary"
log_info "==================================="
log_info "Backup file: $BACKUP_FILE"
log_info "Backup size: $BACKUP_SIZE"
log_info "Total backups: $TOTAL_BACKUPS"
log_info "Total storage: $TOTAL_SIZE"
log_info "Retention: $RETENTION_DAYS days"
log_info "==================================="
echo ""

# Optional: Send notification (uncomment to enable)
# if [ -n "$EMAIL_ADMIN" ]; then
#     echo "Backup completed: $BACKUP_FILE ($BACKUP_SIZE)" | \
#         mail -s "Claude Logistics Backup Success" "$EMAIL_ADMIN"
# fi

exit 0
