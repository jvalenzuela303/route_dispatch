# Troubleshooting Guide - Claude Logistics API

**Common issues and solutions for Claude Logistics API**

---

## Table of Contents

1. [Application Won't Start](#application-wont-start)
2. [Database Issues](#database-issues)
3. [Authentication Problems](#authentication-problems)
4. [API Errors](#api-errors)
5. [Performance Issues](#performance-issues)
6. [Docker Issues](#docker-issues)
7. [SSL/HTTPS Issues](#sslhttps-issues)

---

## Application Won't Start

### Issue: Container exits immediately

**Symptoms**:
- `docker-compose ps` shows app as "Exited"
- Logs show "Error" immediately after start

**Solution**:

```bash
# Check logs for error details
docker-compose -f docker-compose.prod.yml logs app

# Common causes:

# 1. Missing environment variables
# Check .env.prod has all required values
cat .env.prod | grep -v "^#" | grep "="

# 2. Database not ready
# Ensure postgres is healthy first
docker-compose -f docker-compose.prod.yml ps postgres
# Should show "healthy"

# 3. Migration failure
# Check migration logs
docker-compose -f docker-compose.prod.yml logs app | grep "alembic"

# Manual migration
docker-compose -f docker-compose.prod.yml run app alembic upgrade head
```

### Issue: "Port already in use"

**Symptoms**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:8000: bind: address already in use
```

**Solution**:

```bash
# Find process using port
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or change port in docker-compose.prod.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Issue: "Permission denied" errors

**Symptoms**:
```
PermissionError: [Errno 13] Permission denied: '/app/logs'
```

**Solution**:

```bash
# Fix directory permissions
sudo chown -R 1000:1000 /opt/claude-logistics/logs
sudo chown -R 1000:1000 /opt/claude-logistics/backups

# Or in docker-compose.prod.yml, add:
user: "${UID}:${GID}"
```

---

## Database Issues

### Issue: "FATAL: password authentication failed"

**Symptoms**:
- Cannot connect to database
- Authentication errors in logs

**Solution**:

```bash
# 1. Verify credentials in .env.prod
grep DB_ .env.prod

# 2. Verify credentials match database
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "\du"

# 3. Reset password if needed
docker-compose -f docker-compose.prod.yml exec postgres psql -U postgres -c "ALTER USER $DB_USER WITH PASSWORD 'new_password';"

# 4. Update .env.prod and restart
docker-compose -f docker-compose.prod.yml restart app
```

### Issue: "Too many connections"

**Symptoms**:
```
FATAL: sorry, too many clients already
```

**Solution**:

```bash
# 1. Check current connections
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT count(*) FROM pg_stat_activity;"

# 2. Check max connections
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "SHOW max_connections;"

# 3. Kill idle connections
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < current_timestamp - INTERVAL '10 minutes';"

# 4. Increase max_connections (if needed)
# Edit scripts/init_postgis.sql
ALTER SYSTEM SET max_connections = 200;
SELECT pg_reload_conf();

# 5. Restart database
docker-compose -f docker-compose.prod.yml restart postgres
```

### Issue: Slow queries

**Symptoms**:
- API responses are slow
- Database CPU is high

**Solution**:

```bash
# 1. Enable query logging
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries > 1s
SELECT pg_reload_conf();"

# 2. Identify slow queries
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;"

# 3. Check for missing indexes
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT schemaname, tablename, attname
FROM pg_stats
WHERE schemaname = 'public'
AND n_distinct > 100
AND correlation < 0.1;"

# 4. Run ANALYZE
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "ANALYZE;"
```

---

## Authentication Problems

### Issue: "Invalid token" or "Token expired"

**Symptoms**:
- 401 Unauthorized responses
- "Token signature verification failed"

**Solution**:

```bash
# 1. Check token expiration
# JWT tokens expire after 30 minutes by default

# 2. Verify JWT_SECRET_KEY hasn't changed
grep JWT_SECRET_KEY .env.prod

# 3. Generate new token
curl -X POST https://botilleria.com/api/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your_password"

# 4. Use refresh token to get new access token
curl -X POST https://botilleria.com/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token"}'
```

### Issue: "User not found" or "Invalid credentials"

**Symptoms**:
- Cannot log in with correct credentials
- User exists in database

**Solution**:

```bash
# 1. Verify user exists
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT id, username, email, is_active
FROM users
WHERE username = 'admin';"

# 2. Check if user is active
# is_active should be true

# 3. Reset password (if needed)
docker-compose -f docker-compose.prod.yml exec app python -c "
from app.core.security import get_password_hash
print(get_password_hash('new_password'))
"

# Update in database
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
UPDATE users
SET hashed_password = '<hashed_password_from_above>'
WHERE username = 'admin';"
```

### Issue: "Permission denied" (403 Forbidden)

**Symptoms**:
- User is authenticated but cannot access resource
- 403 errors in logs

**Solution**:

```bash
# 1. Check user role and permissions
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
SELECT u.username, r.name as role, p.name as permission
FROM users u
JOIN roles r ON u.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.username = 'problem_user';"

# 2. Check endpoint required permissions
# Review app/api/dependencies/auth.py

# 3. Grant missing permission
docker-compose -f docker-compose.prod.yml exec postgres psql -U $DB_USER -d route_dispatch -c "
INSERT INTO role_permissions (role_id, permission_id)
SELECT
    (SELECT id FROM roles WHERE name = 'Vendedor'),
    (SELECT id FROM permissions WHERE name = 'orders:create')
ON CONFLICT DO NOTHING;"
```

---

## API Errors

### Issue: 500 Internal Server Error

**Symptoms**:
- API returns generic 500 error
- No detailed error message

**Solution**:

```bash
# 1. Check application logs
docker-compose -f docker-compose.prod.yml logs app | grep -i "error\|exception"

# 2. Enable debug mode temporarily (DEVELOPMENT ONLY)
# Edit .env.prod
DEBUG=true

# Restart
docker-compose -f docker-compose.prod.yml restart app

# 3. Reproduce error and check detailed traceback

# 4. Disable debug mode
DEBUG=false
docker-compose -f docker-compose.prod.yml restart app
```

### Issue: 502 Bad Gateway

**Symptoms**:
- Nginx returns 502
- Application is unreachable

**Solution**:

```bash
# 1. Check if app container is running
docker-compose -f docker-compose.prod.yml ps app

# 2. Check app health
curl http://localhost:8000/health  # Direct to container

# 3. Check nginx can reach app
docker-compose -f docker-compose.prod.yml exec nginx ping app

# 4. Check nginx error logs
docker-compose -f docker-compose.prod.yml logs nginx | grep "error"

# 5. Restart services
docker-compose -f docker-compose.prod.yml restart app nginx
```

### Issue: 429 Too Many Requests

**Symptoms**:
- API returns 429 status code
- "rate limit exceeded" message

**Solution**:

```bash
# This is normal rate limiting behavior

# Option 1: Wait for rate limit to reset (usually 1 minute)

# Option 2: Adjust rate limits (if legitimate traffic)
# Edit nginx/conf.d/app.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;  # Increase from 10r/s

# Reload nginx
docker-compose -f docker-compose.prod.yml restart nginx

# Option 3: Whitelist specific IPs (for internal services)
# Add to nginx/conf.d/app.conf
geo $limit {
    default 1;
    192.168.1.0/24 0;  # Don't rate limit this subnet
}

map $limit $limit_key {
    0 "";
    1 $binary_remote_addr;
}

limit_req_zone $limit_key zone=api_limit:10m rate=10r/s;
```

---

## Performance Issues

### Issue: Slow API responses

**Symptoms**:
- Response times > 1 second
- Timeouts

**Solution**:

```bash
# 1. Check database query performance
# See "Slow queries" in Database Issues section

# 2. Check CPU/Memory usage
docker stats --no-stream

# 3. Check if workers are saturated
docker-compose -f docker-compose.prod.yml logs app | grep "worker"

# 4. Scale workers
# Edit .env.prod
UVICORN_WORKERS=8  # Increase

# Restart
docker-compose -f docker-compose.prod.yml restart app

# 5. Enable query caching (if available)
# Check Redis is working
docker-compose -f docker-compose.prod.yml exec redis redis-cli -a $REDIS_PASSWORD ping
```

### Issue: High memory usage

**Symptoms**:
- Container using > 2GB RAM
- OOM (Out of Memory) errors

**Solution**:

```bash
# 1. Check memory usage per container
docker stats --no-stream

# 2. Set memory limits in docker-compose.prod.yml
services:
  app:
    deploy:
      resources:
        limits:
          memory: 2G

# 3. Restart with new limits
docker-compose -f docker-compose.prod.yml up -d

# 4. Monitor for memory leaks
docker-compose -f docker-compose.prod.yml logs app | grep "memory"
```

---

## Docker Issues

### Issue: "No space left on device"

**Solution**:

```bash
# 1. Check disk usage
df -h
docker system df

# 2. Clean up Docker resources
docker system prune -a --volumes

# 3. Remove old images
docker images | grep "<none>" | awk '{print $3}' | xargs docker rmi

# 4. Remove old logs
find /var/lib/docker/containers -name "*.log" -mtime +7 -delete
```

### Issue: Docker daemon not responding

**Solution**:

```bash
# 1. Restart Docker
sudo systemctl restart docker

# 2. Check Docker status
sudo systemctl status docker

# 3. Check Docker logs
sudo journalctl -u docker.service --since "1 hour ago"
```

---

## SSL/HTTPS Issues

### Issue: "Certificate not trusted" warnings

**Solution**:

```bash
# 1. Check certificate expiration
openssl x509 -in nginx/ssl/fullchain.pem -noout -dates

# 2. Check certificate chain
openssl s_client -connect botilleria.com:443 -showcerts

# 3. Renew certificate
./scripts/setup_ssl.sh --prod

# 4. Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

### Issue: Mixed content warnings

**Solution**:

```bash
# Ensure all resources are loaded over HTTPS
# Check CORS_ORIGINS in .env.prod uses https://

# Add HSTS header (already in nginx.conf)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

---

## Getting Help

If issues persist:

1. **Check logs**: `docker-compose -f docker-compose.prod.yml logs`
2. **Review documentation**: DEPLOYMENT_GUIDE.md, OPERATIONS_RUNBOOK.md
3. **Contact support**: admin@botilleria.com
4. **GitHub Issues**: <repository_url>/issues

---

**Last Updated**: January 2026
**Version**: 1.0.0
