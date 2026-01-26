#!/bin/bash
#
# SSL Certificate Setup Script
# Claude Logistics API - Let's Encrypt with Certbot
#
# Usage: ./scripts/setup_ssl.sh [--dev|--prod]
#

set -e

# ============================================
# Configuration
# ============================================
MODE="${1:---dev}"
DOMAIN="${DOMAIN:-botilleria.com}"
EMAIL_ADMIN="${EMAIL_ADMIN:-admin@botilleria.com}"
SSL_DIR="./nginx/ssl"
DHPARAM_FILE="./nginx/dhparam.pem"

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
# Create SSL directory
# ============================================
mkdir -p "$SSL_DIR"

# ============================================
# Development Mode (Self-Signed)
# ============================================
if [ "$MODE" == "--dev" ]; then
    log_info "Setting up DEVELOPMENT SSL certificates (self-signed)..."

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/privkey.pem" \
        -out "$SSL_DIR/fullchain.pem" \
        -subj "/C=CL/ST=Rancagua/L=Rancagua/O=Botilleria/CN=localhost"

    log_info "Self-signed certificate created"
    log_warn "This certificate is for DEVELOPMENT ONLY"
    log_warn "Browsers will show security warnings"
fi

# ============================================
# Production Mode (Let's Encrypt)
# ============================================
if [ "$MODE" == "--prod" ]; then
    log_info "Setting up PRODUCTION SSL certificates (Let's Encrypt)..."

    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        log_info "Installing certbot..."

        # Ubuntu/Debian
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y certbot
        # CentOS/RHEL
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot
        else
            log_warn "Cannot auto-install certbot. Please install manually."
            exit 1
        fi
    fi

    log_info "Obtaining Let's Encrypt certificate for: $DOMAIN"
    log_warn "Make sure:"
    log_warn "  1. Domain DNS points to this server"
    log_warn "  2. Port 80 is open and accessible"
    log_warn "  3. Nginx is stopped"

    read -p "Continue? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Cancelled by user"
        exit 0
    fi

    # Stop nginx if running
    docker-compose -f docker-compose.prod.yml stop nginx 2>/dev/null || true

    # Obtain certificate
    sudo certbot certonly \
        --standalone \
        --preferred-challenges http \
        --email "$EMAIL_ADMIN" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN" \
        -d "www.$DOMAIN"

    # Copy certificates to nginx directory
    sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/"
    sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SSL_DIR/"
    sudo chown $(whoami):$(whoami) "$SSL_DIR/"*.pem

    log_info "Let's Encrypt certificates installed"

    # Setup auto-renewal cron job
    log_info "Setting up auto-renewal..."

    CRON_JOB="0 3 * * * certbot renew --quiet --post-hook 'docker-compose -f $(pwd)/docker-compose.prod.yml restart nginx'"

    (crontab -l 2>/dev/null | grep -v "certbot renew"; echo "$CRON_JOB") | crontab -

    log_info "Auto-renewal configured (runs daily at 3 AM)"
fi

# ============================================
# Generate Diffie-Hellman parameters
# ============================================
if [ ! -f "$DHPARAM_FILE" ]; then
    log_info "Generating Diffie-Hellman parameters (this may take a few minutes)..."
    openssl dhparam -out "$DHPARAM_FILE" 2048
    log_info "DH parameters generated"
else
    log_info "DH parameters already exist: $DHPARAM_FILE"
fi

# ============================================
# Verify certificates
# ============================================
log_info "Verifying SSL setup..."

if [ -f "$SSL_DIR/privkey.pem" ] && [ -f "$SSL_DIR/fullchain.pem" ] && [ -f "$DHPARAM_FILE" ]; then
    log_info "✓ Private key: $SSL_DIR/privkey.pem"
    log_info "✓ Certificate: $SSL_DIR/fullchain.pem"
    log_info "✓ DH params: $DHPARAM_FILE"

    # Show certificate info
    echo ""
    log_info "Certificate details:"
    openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -subject -issuer -dates

    echo ""
    log_info "SSL setup completed successfully!"

    if [ "$MODE" == "--prod" ]; then
        log_info "You can now start nginx with:"
        log_info "  docker-compose -f docker-compose.prod.yml up -d nginx"
    fi
else
    log_warn "SSL setup incomplete. Missing files."
    exit 1
fi

exit 0
