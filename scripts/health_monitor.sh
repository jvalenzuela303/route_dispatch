#!/bin/bash
#
# Health Monitoring Script
# Claude Logistics API - Continuous Health Checks
#
# Usage: ./scripts/health_monitor.sh [--once|--continuous]
#

set -e

# ============================================
# Configuration
# ============================================
MODE="${1:---once}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-http://localhost/health}"
CHECK_INTERVAL="${CHECK_INTERVAL:-60}"  # seconds
EMAIL_ADMIN="${EMAIL_ADMIN:-}"
ALERT_THRESHOLD="${ALERT_THRESHOLD:-3}"  # consecutive failures before alert
LOG_FILE="${LOG_FILE:-./logs/health_monitor.log}"

# Failure counter
FAILURE_COUNT=0
LAST_ALERT_TIME=0
ALERT_COOLDOWN=3600  # 1 hour between alerts

# ============================================
# Color output
# ============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

# ============================================
# Alert Functions
# ============================================
send_alert() {
    local subject="$1"
    local message="$2"

    log_error "$subject: $message"

    # Send email if configured
    if [ -n "$EMAIL_ADMIN" ] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "🚨 Claude Logistics ALERT: $subject" "$EMAIL_ADMIN"
        log_info "Alert email sent to $EMAIL_ADMIN"
    fi

    # Could also integrate with: Slack, PagerDuty, SMS, etc.
}

restart_services() {
    log_warn "Attempting to restart services..."

    if docker-compose -f docker-compose.prod.yml restart app nginx; then
        log_info "Services restarted successfully"
        send_alert "Auto-Recovery" "Services were automatically restarted due to health check failures"
        FAILURE_COUNT=0
        return 0
    else
        log_error "Failed to restart services"
        send_alert "Auto-Recovery FAILED" "Attempted to restart services but failed. Manual intervention required!"
        return 1
    fi
}

# ============================================
# Health Check Function
# ============================================
perform_health_check() {
    local start_time=$(date +%s)

    # Perform HTTP health check
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_ENDPOINT" 2>/dev/null || echo "000")
    local response_time=$(($(date +%s) - start_time))

    # Check individual services
    local db_status="UNKNOWN"
    local redis_status="UNKNOWN"
    local app_status="UNKNOWN"
    local nginx_status="UNKNOWN"

    # Docker container status
    if docker ps --format '{{.Names}}:{{.Status}}' | grep -q "claude_logistics_db_prod.*Up"; then
        db_status="UP"
    else
        db_status="DOWN"
    fi

    if docker ps --format '{{.Names}}:{{.Status}}' | grep -q "claude_logistics_cache_prod.*Up"; then
        redis_status="UP"
    else
        redis_status="DOWN"
    fi

    if docker ps --format '{{.Names}}:{{.Status}}' | grep -q "claude_logistics_app_prod.*Up"; then
        app_status="UP"
    else
        app_status="DOWN"
    fi

    if docker ps --format '{{.Names}}:{{.Status}}' | grep -q "claude_logistics_nginx_prod.*Up"; then
        nginx_status="UP"
    else
        nginx_status="DOWN"
    fi

    # Evaluate health
    if [ "$http_code" == "200" ] && [ "$db_status" == "UP" ] && [ "$app_status" == "UP" ] && [ "$nginx_status" == "UP" ]; then
        log_info "✓ Health check PASSED (HTTP $http_code, ${response_time}s) - DB:$db_status Redis:$redis_status App:$app_status Nginx:$nginx_status"
        FAILURE_COUNT=0
        return 0
    else
        ((FAILURE_COUNT++))
        log_error "✗ Health check FAILED (HTTP $http_code, ${response_time}s) - DB:$db_status Redis:$redis_status App:$app_status Nginx:$nginx_status"

        # Check if we should alert
        if [ $FAILURE_COUNT -ge $ALERT_THRESHOLD ]; then
            local current_time=$(date +%s)
            local time_since_last_alert=$((current_time - LAST_ALERT_TIME))

            if [ $time_since_last_alert -ge $ALERT_COOLDOWN ]; then
                send_alert "Service Unhealthy" "Health check failed $FAILURE_COUNT consecutive times.\n\nStatus:\n- HTTP: $http_code\n- Database: $db_status\n- Redis: $redis_status\n- App: $app_status\n- Nginx: $nginx_status"
                LAST_ALERT_TIME=$current_time

                # Attempt auto-recovery
                restart_services
            fi
        fi

        return 1
    fi
}

# ============================================
# Resource Monitoring
# ============================================
check_resources() {
    log_info "Checking system resources..."

    # Docker container stats
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
        claude_logistics_db_prod \
        claude_logistics_cache_prod \
        claude_logistics_app_prod \
        claude_logistics_nginx_prod 2>/dev/null || log_warn "Cannot get container stats"

    # Disk usage
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 80 ]; then
        log_warn "Disk usage is high: ${disk_usage}%"
        send_alert "High Disk Usage" "Disk usage has reached ${disk_usage}%"
    fi

    # Database connections
    if [ "$db_status" == "UP" ]; then
        local db_connections=$(docker exec claude_logistics_db_prod psql -U $DB_USER -d route_dispatch -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | tr -d ' ')
        log_info "Active database connections: $db_connections"
    fi
}

# ============================================
# Main Execution
# ============================================
mkdir -p "$(dirname "$LOG_FILE")"

log_info "Starting health monitor (mode: $MODE)"

if [ "$MODE" == "--once" ]; then
    perform_health_check
    check_resources
    exit $?
fi

if [ "$MODE" == "--continuous" ]; then
    log_info "Running continuous monitoring (interval: ${CHECK_INTERVAL}s)"

    while true; do
        perform_health_check

        # Check resources every 10 checks
        if [ $(($(date +%s) % 600)) -eq 0 ]; then
            check_resources
        fi

        sleep "$CHECK_INTERVAL"
    done
fi

exit 0
