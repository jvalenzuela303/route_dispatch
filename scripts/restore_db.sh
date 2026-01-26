#!/bin/bash
#
# Database Restore Script
# Claude Logistics API - PostgreSQL + PostGIS
#
# Usage: ./scripts/restore_db.sh <backup_file> [--confirm]
#

set -e  # Exit on error
set -o pipefail  # Catch errors in pipes

# ============================================
# Configuration
# ============================================
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="route_dispatch"
DB_USER="${DB_USER:-claude_admin}"
BACKUP_FILE="$1"
CONFIRM_FLAG="$2"

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
# Validate Input
# ============================================
if [ -z "$BACKUP_FILE" ]; then
    log_error "No backup file specified!"
    echo ""
    echo "Usage: $0 <backup_file> [--confirm]"
    echo ""
    echo "Available backups:"
    find /backups -name "route_dispatch_*.sql.gz" -type f -printf "  %p (%TY-%Tm-%Td %TH:%TM) - %s bytes\n" | sort -r
    exit 1
fi

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# ============================================
# Confirmation Prompt
# ============================================
echo ""
log_warn "⚠️  WARNING: DATABASE RESTORE OPERATION ⚠️"
echo ""
echo "This will:"
echo "  1. Stop the application container"
echo "  2. DROP the existing database '$DB_NAME'"
echo "  3. Restore from: $BACKUP_FILE"
echo "  4. Restart the application container"
echo ""
log_warn "ALL CURRENT DATA WILL BE LOST!"
echo ""

if [ "$CONFIRM_FLAG" != "--confirm" ]; then
    read -p "Are you sure you want to proceed? (type 'yes' to confirm): " CONFIRMATION

    if [ "$CONFIRMATION" != "yes" ]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# ============================================
# Pre-Restore Steps
# ============================================
log_info "Starting restore process at $(date)"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    log_error "docker-compose not found. Please install docker-compose."
    exit 1
fi

# Check if pg_restore is available
if ! command -v pg_restore &> /dev/null; then
    log_error "pg_restore not found. Please install postgresql-client."
    exit 1
fi

# ============================================
# Step 1: Stop Application
# ============================================
log_info "Step 1/5: Stopping application container..."

if docker ps --format '{{.Names}}' | grep -q "claude_logistics_app"; then
    docker-compose -f docker-compose.prod.yml stop app
    log_info "Application stopped"
else
    log_warn "Application container not running"
fi

sleep 2

# ============================================
# Step 2: Create Backup of Current State
# ============================================
log_info "Step 2/5: Creating safety backup of current state..."

SAFETY_BACKUP="/backups/pre_restore_safety_$(date +%Y%m%d_%H%M%S).sql.gz"

if PGPASSWORD=$DB_PASSWORD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME > /dev/null 2>&1; then
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --format=custom \
        | gzip > "$SAFETY_BACKUP"

    log_info "Safety backup created: $SAFETY_BACKUP"
else
    log_warn "Cannot create safety backup - database not accessible"
fi

# ============================================
# Step 3: Drop and Recreate Database
# ============================================
log_info "Step 3/5: Dropping and recreating database..."

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres <<EOF
-- Terminate existing connections
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = '$DB_NAME'
  AND pid <> pg_backend_pid();

-- Drop database
DROP DATABASE IF EXISTS $DB_NAME;

-- Recreate database
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOF

log_info "Database recreated"

# Enable PostGIS extension
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF

log_info "PostGIS extensions enabled"

# ============================================
# Step 4: Restore Backup
# ============================================
log_info "Step 4/5: Restoring database from backup..."
log_info "Backup file: $BACKUP_FILE"

# Decompress and restore
gunzip -c "$BACKUP_FILE" | PGPASSWORD=$DB_PASSWORD pg_restore \
    -h $DB_HOST \
    -p $DB_PORT \
    -U $DB_USER \
    -d $DB_NAME \
    --no-owner \
    --no-acl \
    --verbose \
    --exit-on-error 2>&1 | tee /tmp/restore_log.txt

if [ ${PIPESTATUS[1]} -eq 0 ]; then
    log_info "Database restored successfully"
else
    log_error "Restore failed! Check /tmp/restore_log.txt for details"
    log_info "You can restore from safety backup: $SAFETY_BACKUP"
    exit 1
fi

# ============================================
# Step 5: Restart Application
# ============================================
log_info "Step 5/5: Restarting application..."

docker-compose -f docker-compose.prod.yml start app

# Wait for app to be healthy
log_info "Waiting for application to become healthy..."
sleep 5

MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f http://localhost/health > /dev/null 2>&1; then
        log_info "Application is healthy!"
        break
    fi

    ((RETRY_COUNT++))
    echo -n "."
    sleep 2
done

echo ""

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_warn "Application health check timeout. Check logs with:"
    log_warn "docker-compose -f docker-compose.prod.yml logs -f app"
fi

# ============================================
# Verification
# ============================================
log_info "Verifying restore..."

# Count records in key tables
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
\echo 'Database Statistics:'
\echo '===================='
SELECT 'users' AS table_name, COUNT(*) AS count FROM users
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'invoices', COUNT(*) FROM invoices
UNION ALL
SELECT 'routes', COUNT(*) FROM routes
ORDER BY table_name;
EOF

# ============================================
# Summary
# ============================================
echo ""
log_info "==================================="
log_info "Restore Summary"
log_info "==================================="
log_info "Backup file: $BACKUP_FILE"
log_info "Database: $DB_NAME"
log_info "Safety backup: $SAFETY_BACKUP"
log_info "Status: COMPLETED"
log_info "==================================="
echo ""

log_info "Restore completed successfully at $(date)"

# Optional: Send notification (uncomment to enable)
# if [ -n "$EMAIL_ADMIN" ]; then
#     echo "Database restored from: $BACKUP_FILE" | \
#         mail -s "Claude Logistics Restore Complete" "$EMAIL_ADMIN"
# fi

exit 0
