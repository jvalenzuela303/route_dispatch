# Operations Runbook - Claude Logistics API

**Operational procedures and troubleshooting for production environments**

---

## Table of Contents

1. [Common Operations](#common-operations)
2. [Emergency Procedures](#emergency-procedures)
3. [Monitoring & Alerts](#monitoring--alerts)
4. [Backup & Recovery](#backup--recovery)
5. [Performance Tuning](#performance-tuning)
6. [Security Incidents](#security-incidents)

---

## Common Operations

### Starting Services

```bash
# Start all services
cd /opt/claude-logistics
docker-compose -f docker-compose.prod.yml up -d

# Start specific service
docker-compose -f docker-compose.prod.yml up -d app
docker-compose -f docker-compose.prod.yml up -d nginx
```

### Stopping Services

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml stop

# Stop specific service
docker-compose -f docker-compose.prod.yml stop app

# Force stop (if hung)
docker-compose -f docker-compose.prod.yml kill app
```

### Restarting Services

```bash
# Restart all services
docker-compose -f docker-compose.prod.yml restart

# Restart application only (zero downtime)
docker-compose -f docker-compose.prod.yml restart app

# Restart nginx (to reload config)
docker-compose -f docker-compose.prod.yml restart nginx
```

### Viewing Logs

```bash
# Tail all logs
docker-compose -f docker-compose.prod.yml logs -f

# Tail specific service
docker-compose -f docker-compose.prod.yml logs -f app
docker-compose -f docker-compose.prod.yml logs -f postgres

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100 app

# Grep for errors
docker-compose -f docker-compose.prod.yml logs app | grep -i error
```

### Checking Service Status

```bash
# All services
docker-compose -f docker-compose.prod.yml ps

# Detailed container info
docker ps -a --filter name=claude_logistics

# Resource usage
docker stats --no-stream

# Health check
curl https://botilleria.com/health
```

### Accessing Containers

```bash
# Application shell
docker-compose -f docker-compose.prod.yml exec app bash

# Database shell
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch

# Redis CLI
docker-compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD
```

---

## Emergency Procedures

### Service Down

**Symptoms**: Health check failing, 502/503 errors

**Immediate Actions**:

```bash
# 1. Check container status
docker-compose -f docker-compose.prod.yml ps

# 2. Check logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=50 app

# 3. Restart affected service
docker-compose -f docker-compose.prod.yml restart app

# 4. If still failing, rebuild and restart
docker-compose -f docker-compose.prod.yml build app
docker-compose -f docker-compose.prod.yml up -d app

# 5. Verify health
curl https://botilleria.com/health
```

**Root Cause Analysis**:

```bash
# Check system resources
df -h            # Disk space
free -h          # Memory
top              # CPU usage

# Check Docker logs
journalctl -u docker.service --since "10 minutes ago"

# Check application logs
docker-compose -f docker-compose.prod.yml logs app | grep -i "error\|exception\|fatal"
```

### Database Connection Issues

**Symptoms**: "Connection refused", "Connection timeout"

**Immediate Actions**:

```bash
# 1. Check if PostgreSQL is running
docker-compose -f docker-compose.prod.yml ps postgres

# 2. Check PostgreSQL logs
docker-compose -f docker-compose.prod.yml logs postgres

# 3. Test connectivity
docker-compose -f docker-compose.prod.yml exec app ping postgres

# 4. Check connection pool
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "SELECT count(*) FROM pg_stat_activity;"

# 5. Restart PostgreSQL if needed
docker-compose -f docker-compose.prod.yml restart postgres
```

### High CPU Usage

**Symptoms**: Slow response times, high load average

**Immediate Actions**:

```bash
# 1. Identify container using most CPU
docker stats --no-stream

# 2. Check running queries (if database is the issue)
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT pid, age(clock_timestamp(), query_start), usename, query
FROM pg_stat_activity
WHERE query != '<IDLE>' AND query NOT ILIKE '%pg_stat_activity%'
ORDER BY query_start DESC;"

# 3. Kill long-running queries if needed
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "SELECT pg_terminate_backend(<pid>);"

# 4. Check application workers
docker-compose -f docker-compose.prod.yml logs app | grep "worker"

# 5. Scale workers if needed (temporary)
docker-compose -f docker-compose.prod.yml up -d --scale app=2
```

### Out of Disk Space

**Symptoms**: "No space left on device"

**Immediate Actions**:

```bash
# 1. Check disk usage
df -h
du -sh /var/lib/docker/
du -sh /opt/claude-logistics/logs/
du -sh /opt/claude-logistics/backups/

# 2. Remove old Docker images
docker system prune -a --volumes

# 3. Remove old logs
find /opt/claude-logistics/logs -name "*.log" -mtime +7 -delete

# 4. Remove old backups (keep last 7 days)
find /opt/claude-logistics/backups -name "*.sql.gz" -mtime +7 -delete

# 5. Restart services
docker-compose -f docker-compose.prod.yml restart
```

### SSL Certificate Expiration

**Symptoms**: "Certificate expired", browser warnings

**Immediate Actions**:

```bash
# 1. Check certificate expiration
openssl x509 -in nginx/ssl/fullchain.pem -noout -dates

# 2. Renew Let's Encrypt certificate
sudo certbot renew --force-renewal

# 3. Copy new certificates
sudo cp /etc/letsencrypt/live/botilleria.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/botilleria.com/privkey.pem nginx/ssl/

# 4. Reload nginx
docker-compose -f docker-compose.prod.yml restart nginx

# 5. Verify
curl -I https://botilleria.com
```

---

## Monitoring & Alerts

### Health Check Monitoring

```bash
# Manual health check
./scripts/health_monitor.sh --once

# Continuous monitoring (runs in background)
nohup ./scripts/health_monitor.sh --continuous > /dev/null 2>&1 &

# Check monitoring process
ps aux | grep health_monitor

# View monitoring log
tail -f logs/health_monitor.log
```

### Key Metrics to Monitor

1. **Application Health**: `GET /health` should return 200
2. **Response Time**: P95 should be < 500ms
3. **Database Connections**: Should be < 80% of max_connections
4. **CPU Usage**: Should be < 80%
5. **Memory Usage**: Should be < 80%
6. **Disk Space**: Should have > 20% free
7. **Error Rate**: Should be < 1%

### Setting Up External Monitoring

**Uptime Robot** (Free):
```bash
# Add monitor for: https://botilleria.com/health
# Alert interval: 5 minutes
# Alert contacts: admin@botilleria.com
```

**UptimeRobot API**:
```bash
curl -X POST "https://api.uptimerobot.com/v2/newMonitor" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "api_key=YOUR_API_KEY" \
  -d "friendly_name=Claude Logistics" \
  -d "url=https://botilleria.com/health" \
  -d "type=1"
```

---

## Backup & Recovery

### Creating Backups

```bash
# Full backup
./scripts/backup_db.sh --full

# Schema only
./scripts/backup_db.sh --schema-only

# Data only
./scripts/backup_db.sh --data-only

# Verify backup created
ls -lh backups/
```

### Restoring from Backup

```bash
# List available backups
ls -lh backups/

# Restore (with confirmation prompt)
./scripts/restore_db.sh /backups/route_dispatch_full_20260122_020000.sql.gz

# Restore (skip confirmation)
./scripts/restore_db.sh /backups/route_dispatch_full_20260122_020000.sql.gz --confirm
```

### Backup to Remote Storage

**AWS S3**:
```bash
# Install AWS CLI
sudo apt-get install awscli

# Configure credentials
aws configure

# Sync backups to S3
aws s3 sync /opt/claude-logistics/backups/ s3://claude-logistics-backups/

# Automate with cron
echo "0 3 * * * aws s3 sync /opt/claude-logistics/backups/ s3://claude-logistics-backups/" | crontab -
```

**rsync to remote server**:
```bash
# One-time sync
rsync -avz /opt/claude-logistics/backups/ user@backup-server:/backups/claude-logistics/

# Automated sync (add to crontab)
0 3 * * * rsync -avz /opt/claude-logistics/backups/ user@backup-server:/backups/claude-logistics/
```

---

## Performance Tuning

### Database Optimization

```bash
# Run VACUUM ANALYZE
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "VACUUM ANALYZE;"

# Check table sizes
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# Check index usage
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;"

# Check slow queries
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"
```

### Application Tuning

```bash
# Adjust Uvicorn workers
# Edit .env.prod
UVICORN_WORKERS=8  # (2 x CPU cores) + 1

# Restart application
docker-compose -f docker-compose.prod.yml restart app

# Monitor worker performance
docker-compose -f docker-compose.prod.yml logs app | grep "worker"
```

### Nginx Tuning

```bash
# Edit nginx.conf
nano nginx/nginx.conf

# Increase worker connections
worker_connections 8192;

# Adjust rate limits
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;

# Reload nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

---

## Security Incidents

### Suspected Unauthorized Access

**Immediate Actions**:

```bash
# 1. Check access logs
docker-compose -f docker-compose.prod.yml logs nginx | grep -E "POST|PUT|DELETE"

# 2. Check authentication failures
docker-compose -f docker-compose.prod.yml logs app | grep "401\|403"

# 3. Block suspicious IP (if identified)
sudo ufw deny from <suspicious_ip>

# 4. Review audit logs
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100;"

# 5. Rotate JWT secrets if compromised
# Edit .env.prod with new JWT_SECRET_KEY
docker-compose -f docker-compose.prod.yml restart app
```

### DDoS or Abuse

**Immediate Actions**:

```bash
# 1. Check request rate
docker-compose -f docker-compose.prod.yml logs nginx | awk '{print $1}' | sort | uniq -c | sort -nr | head

# 2. Tighten rate limits temporarily
# Edit nginx/conf.d/app.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=5r/s;

# 3. Reload nginx
docker-compose -f docker-compose.prod.yml restart nginx

# 4. Block abusive IPs
sudo ufw deny from <abusive_ip>

# 5. Consider enabling Cloudflare or similar DDoS protection
```

### Data Breach

**Immediate Actions**:

```bash
# 1. Take service offline immediately
docker-compose -f docker-compose.prod.yml stop

# 2. Create forensic backup
./scripts/backup_db.sh --full

# 3. Review audit logs for unauthorized access
# 4. Contact security team
# 5. Follow incident response plan
# 6. Notify affected users (if required by law)
```

---

## Scheduled Maintenance

### Weekly Maintenance Window

**Recommended**: Sundays 2:00 AM - 4:00 AM

```bash
# 1. Notify users (via API or email)

# 2. Create pre-maintenance backup
./scripts/backup_db.sh --full

# 3. Stop application
docker-compose -f docker-compose.prod.yml stop app

# 4. Database maintenance
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "VACUUM FULL ANALYZE;"

# 5. Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# 6. Restart services
docker-compose -f docker-compose.prod.yml up -d

# 7. Verify health
./scripts/health_monitor.sh --once

# 8. Notify users (maintenance complete)
```

---

## Contact Information

- **Primary**: admin@botilleria.com
- **Emergency**: +56 9 XXXX XXXX
- **On-Call**: Check PagerDuty schedule

---

**Last Updated**: January 2026
**Version**: 1.0.0
