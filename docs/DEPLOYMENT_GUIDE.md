# Deployment Guide - Claude Logistics API

**Production Deployment Guide for Claude Logistics API**
Complete step-by-step instructions for deploying to production environments.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Initial Setup](#initial-setup)
4. [SSL Configuration](#ssl-configuration)
5. [Deployment Steps](#deployment-steps)
6. [Post-Deployment](#post-deployment)
7. [Rollback Procedure](#rollback-procedure)
8. [Cloud Deployment](#cloud-deployment)

---

## Prerequisites

### System Requirements

- **Operating System**: Ubuntu 20.04+ or Debian 11+
- **RAM**: Minimum 4GB, Recommended 8GB
- **CPU**: Minimum 2 cores, Recommended 4 cores
- **Storage**: Minimum 50GB SSD
- **Network**: Static IP address, Domain name configured

### Software Requirements

```bash
# Docker and Docker Compose
Docker version 20.10+
Docker Compose version 2.0+

# Database
PostgreSQL 14+ with PostGIS 3.0+

# Optional
certbot (for Let's Encrypt SSL)
```

### Access Requirements

- **SSH access** to production server
- **Root or sudo** privileges
- **Domain DNS** configured (A records pointing to server IP)
- **SMTP credentials** for email notifications
- **Backup storage** (local or cloud)

---

## Pre-Deployment Checklist

### Security

- [ ] Generate strong passwords for all services
- [ ] Generate JWT secret key (≥64 characters)
- [ ] Configure firewall (UFW recommended)
- [ ] Disable password authentication for SSH (use keys only)
- [ ] Configure fail2ban for brute-force protection
- [ ] Review and update CORS_ORIGINS

### Configuration

- [ ] `.env.prod` configured with production values
- [ ] SMTP settings verified and tested
- [ ] Database credentials configured
- [ ] Redis password set
- [ ] Domain SSL certificates obtained
- [ ] Backup retention policy defined

### Infrastructure

- [ ] Server provisioned and accessible
- [ ] DNS records configured (A, AAAA, CNAME if needed)
- [ ] Firewall rules configured (allow 80, 443, 22)
- [ ] Monitoring and alerting configured
- [ ] Backup storage available

---

## Initial Setup

### 1. Server Preparation

```bash
# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y \
    curl \
    git \
    ufw \
    fail2ban \
    postgresql-client \
    openssl

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable

# Enable fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 3. Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/claude-logistics
sudo chown $USER:$USER /opt/claude-logistics

# Clone repository
cd /opt/claude-logistics
git clone <repository_url> .

# Or copy files via rsync/scp
# rsync -avz --exclude node_modules local_dir/ user@server:/opt/claude-logistics/
```

---

## SSL Configuration

### Option 1: Let's Encrypt (Recommended for Production)

```bash
cd /opt/claude-logistics

# Set environment variables
export DOMAIN=botilleria.com
export EMAIL_ADMIN=admin@botilleria.com

# Run SSL setup script
./scripts/setup_ssl.sh --prod

# Verify certificates
ls -l nginx/ssl/
# Should show: fullchain.pem, privkey.pem

# Verify DH parameters
ls -l nginx/dhparam.pem
```

### Option 2: Self-Signed (Development/Testing)

```bash
# Generate self-signed certificates
./scripts/setup_ssl.sh --dev

# Note: Browsers will show security warnings
```

### Option 3: Custom Certificates

```bash
# Copy your certificates
cp /path/to/fullchain.pem nginx/ssl/
cp /path/to/privkey.pem nginx/ssl/

# Generate DH parameters
openssl dhparam -out nginx/dhparam.pem 2048
```

---

## Deployment Steps

### Step 1: Configure Environment

```bash
cd /opt/claude-logistics

# Copy environment template
cp .env.prod.example .env.prod

# Edit production environment
nano .env.prod

# Required values:
# - DB_USER=claude_admin
# - DB_PASSWORD=<strong_password>
# - REDIS_PASSWORD=<strong_password>
# - JWT_SECRET_KEY=<64_char_secret>
# - SMTP_HOST, SMTP_USER, SMTP_PASSWORD
# - CORS_ORIGINS=https://botilleria.com
# - DOMAIN=botilleria.com
```

**Generate secure secrets:**

```bash
# Database password
openssl rand -base64 32

# Redis password
openssl rand -base64 32

# JWT secret key
openssl rand -hex 64
```

### Step 2: Verify Configuration

```bash
# Check Docker Compose configuration
docker-compose -f docker-compose.prod.yml config

# Should not show any errors
# Review the output for correct values
```

### Step 3: Create Required Directories

```bash
# Create directories for volumes
mkdir -p logs
mkdir -p logs/nginx
mkdir -p backups
mkdir -p nginx/ssl

# Set permissions
chmod 700 backups
chmod 755 logs
```

### Step 4: Build Images

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build --no-cache

# Tag images with version
docker tag claude_logistics_app:latest claude_logistics_app:1.0.0
```

### Step 5: Start Services

```bash
# Start database and Redis first
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for database to be ready
docker-compose -f docker-compose.prod.yml logs -f postgres
# Wait for: "database system is ready to accept connections"

# Start application
docker-compose -f docker-compose.prod.yml up -d app

# Wait for migrations to complete
docker-compose -f docker-compose.prod.yml logs -f app
# Wait for: "Migrations completed!"

# Start Nginx
docker-compose -f docker-compose.prod.yml up -d nginx
```

### Step 6: Verify Deployment

```bash
# Check all containers are running
docker-compose -f docker-compose.prod.yml ps

# Should show all services as "Up" and "healthy"

# Check logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=100

# Test health endpoint (local)
curl http://localhost/health

# Test health endpoint (public)
curl https://botilleria.com/health
```

### Step 7: Create Initial Admin User

```bash
# Access application container
docker-compose -f docker-compose.prod.yml exec app bash

# Run user creation script (if available)
python -m app.scripts.create_admin_user

# Or use API
curl -X POST https://botilleria.com/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@botilleria.com",
    "password": "SecureP@ssw0rd!",
    "role_id": "<admin_role_uuid>"
  }'

# Exit container
exit
```

---

## Post-Deployment

### 1. Setup Automated Backups

```bash
# Install cron jobs
./scripts/setup_cron.sh

# Verify cron jobs
crontab -l

# Test manual backup
./scripts/backup_db.sh --full

# Verify backup created
ls -lh backups/
```

### 2. Configure Monitoring

```bash
# Test health monitor
./scripts/health_monitor.sh --once

# Setup continuous monitoring (optional)
nohup ./scripts/health_monitor.sh --continuous &
```

### 3. Configure Log Rotation

```bash
# Docker logs are already configured in docker-compose.prod.yml
# Verify log rotation settings
docker inspect claude_logistics_app_prod | grep -A 5 "LogConfig"

# Application logs (if needed)
sudo nano /etc/logrotate.d/claude-logistics
```

Example logrotate configuration:

```
/opt/claude-logistics/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker-compose -f /opt/claude-logistics/docker-compose.prod.yml restart app > /dev/null 2>&1 || true
    endscript
}
```

### 4. Performance Tuning

```bash
# View container resource usage
docker stats

# Adjust Uvicorn workers if needed
# Edit .env.prod: UVICORN_WORKERS=8 (for 4 CPU cores)

# Restart application
docker-compose -f docker-compose.prod.yml restart app
```

### 5. Security Hardening

```bash
# Enable automatic security updates
sudo apt-get install unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades

# Configure SSH (disable password auth)
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd

# Review fail2ban jails
sudo fail2ban-client status
```

---

## Rollback Procedure

### Quick Rollback

```bash
# Stop current deployment
docker-compose -f docker-compose.prod.yml down

# Restore database from backup
./scripts/restore_db.sh /backups/pre_deployment_backup.sql.gz --confirm

# Checkout previous version
git checkout <previous_commit_hash>

# Rebuild and start
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### Zero-Downtime Rollback (Blue-Green)

```bash
# Keep old containers running
# Deploy new version to different ports

# If new version fails, simply redirect traffic back
docker-compose -f docker-compose.prod.yml stop nginx
docker-compose -f docker-compose.old.yml start nginx
```

---

## Cloud Deployment

### AWS (EC2 + RDS)

```bash
# Use RDS for PostgreSQL with PostGIS
# Deploy application to EC2 or ECS
# Use ELB for load balancing
# Use Route 53 for DNS
# Use S3 for backups

# Environment adjustments:
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/route_dispatch
```

### Google Cloud (Cloud Run + Cloud SQL)

```bash
# Deploy to Cloud Run
gcloud run deploy claude-logistics \
  --image gcr.io/project-id/claude-logistics \
  --platform managed \
  --region us-central1 \
  --add-cloudsql-instances PROJECT:REGION:INSTANCE

# Use Cloud SQL for PostgreSQL
# Use Cloud Storage for backups
```

### Azure (App Service + PostgreSQL)

```bash
# Deploy to Azure App Service
az webapp create \
  --resource-group claude-logistics \
  --plan claude-logistics-plan \
  --name claude-logistics \
  --runtime "PYTHON:3.11"

# Use Azure Database for PostgreSQL
# Use Azure Blob Storage for backups
```

---

## Maintenance

### Regular Tasks

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f app

# Restart services
docker-compose -f docker-compose.prod.yml restart app

# Update application
git pull
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Database backup
./scripts/backup_db.sh --full

# Database restore
./scripts/restore_db.sh /backups/backup_file.sql.gz

# Health check
./scripts/health_monitor.sh --once
```

---

## Support

For issues or questions:
- Check logs: `docker-compose -f docker-compose.prod.yml logs`
- Review TROUBLESHOOTING.md
- Review OPERATIONS_RUNBOOK.md
- Contact: admin@botilleria.com

---

**Last Updated**: January 2026
**Version**: 1.0.0
**Maintainer**: Claude Logistics Team
