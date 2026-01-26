#!/bin/bash
#
# Setup Cron Jobs for Claude Logistics API
# Automated backups, monitoring, and maintenance
#
# Usage: ./scripts/setup_cron.sh
#

set -e

# ============================================
# Configuration
# ============================================
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

# ============================================
# Color output
# ============================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# ============================================
# Create log directory
# ============================================
mkdir -p "$LOG_DIR"

# ============================================
# Backup existing crontab
# ============================================
log_info "Backing up existing crontab..."
crontab -l > "$PROJECT_DIR/crontab.backup" 2>/dev/null || echo "# No existing crontab" > "$PROJECT_DIR/crontab.backup"
log_info "Backup saved to: $PROJECT_DIR/crontab.backup"

# ============================================
# Define Cron Jobs
# ============================================

# Remove any existing Claude Logistics cron jobs
crontab -l 2>/dev/null | grep -v "Claude Logistics" > /tmp/new_cron || true

# Add new cron jobs
cat >> /tmp/new_cron <<EOF

# ============================================
# Claude Logistics API - Automated Tasks
# ============================================

# Daily full backup at 2:00 AM
0 2 * * * cd $PROJECT_DIR && ./scripts/backup_db.sh --full >> $LOG_DIR/backup.log 2>&1

# Health check every 5 minutes
*/5 * * * * cd $PROJECT_DIR && ./scripts/health_monitor.sh --once >> $LOG_DIR/health_monitor.log 2>&1

# Weekly schema-only backup (Sundays at 3:00 AM)
0 3 * * 0 cd $PROJECT_DIR && ./scripts/backup_db.sh --schema-only >> $LOG_DIR/backup_schema.log 2>&1

# Clean old logs (keep last 30 days) - Daily at 4:00 AM
0 4 * * * find $LOG_DIR -name "*.log" -mtime +30 -delete

# Restart services weekly (Sundays at 5:00 AM for maintenance)
0 5 * * 0 cd $PROJECT_DIR && docker-compose -f docker-compose.prod.yml restart app >> $LOG_DIR/restart.log 2>&1

# Generate daily operations report (Daily at 6:00 AM)
0 6 * * * curl -s "http://localhost/api/reports/daily-operations" >> $LOG_DIR/daily_report.log 2>&1

# Database vacuum analyze (Daily at 1:00 AM)
0 1 * * * docker exec claude_logistics_db_prod psql -U \$DB_USER -d route_dispatch -c "VACUUM ANALYZE;" >> $LOG_DIR/vacuum.log 2>&1

# ============================================
# End Claude Logistics API Tasks
# ============================================
EOF

# ============================================
# Install new crontab
# ============================================
log_info "Installing new crontab..."
crontab /tmp/new_cron
rm /tmp/new_cron

# ============================================
# Display installed cron jobs
# ============================================
echo ""
log_info "Cron jobs installed successfully!"
echo ""
log_info "Scheduled tasks:"
echo "  • Daily full backup: 2:00 AM"
echo "  • Health check: Every 5 minutes"
echo "  • Weekly schema backup: Sundays 3:00 AM"
echo "  • Log cleanup: Daily 4:00 AM"
echo "  • Weekly restart: Sundays 5:00 AM"
echo "  • Daily report: Daily 6:00 AM"
echo "  • Database vacuum: Daily 1:00 AM"
echo ""

log_info "View all cron jobs:"
log_info "  crontab -l"
echo ""

log_info "View cron logs:"
log_info "  tail -f $LOG_DIR/backup.log"
log_info "  tail -f $LOG_DIR/health_monitor.log"
echo ""

log_warn "Make sure the following are configured in .env.prod:"
log_warn "  • DB_USER and DB_PASSWORD"
log_warn "  • EMAIL_ADMIN (for alerts)"
echo ""

exit 0
