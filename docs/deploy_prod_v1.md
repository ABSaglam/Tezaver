# Tezaver Bulut - Production Deployment (v1)

## Overview
This guide covers deploying Tezaver Bulut v0.33+ in a hardened production environment.

## 1. Environment Configuration
Create a `.env` file or set environment variables in your container/system.

```bash
# Core
TEZAVER_OPS_TOKEN=very_secret_token_here_change_me
DEPLOY_ENV=PROD

# Network Hardening
ALLOWED_HOSTS=bulut.example.com,127.0.0.1
CORS_ALLOWED_ORIGINS=https://bulut.example.com
TRUST_PROXY_HEADERS=true
SECURE_HEADERS_ENABLED=true
BASIC_RATE_LIMIT_ENABLED=true
BASIC_RATE_LIMIT_RPS=10

# Database
SQLITE_PATH=/data/tezaver.db

# Binance (Real Trade)
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=yyy
MODE=REAL
EXECUTION_ENABLED=true
```

## 2. Reverse Proxy Setup

Tezaver Bulut should **ALWAYS** be run behind a reverse proxy (Caddy or Nginx) in production to handle SSL/TLS and act as a first line of defense.

### Option A: Caddy (Recommended)
Caddy automatically manages HTTPS certificates.

**Caddyfile:**
```caddy
bulut.example.com {
    # Security Headers (Proxy layer)
    header Strict-Transport-Security "max-age=31536000; includeSubDomains"
    
    # Backend API
    handle /api/* {
        reverse_proxy localhost:8000
    }
    
    # OpenAPI Docs (Optional: Protect or Block)
    handle /docs {
        reverse_proxy localhost:8000
    }
    
    # Streamlit UI
    handle /* {
        reverse_proxy localhost:8501
    }
}
```

### Option B: Nginx
```nginx
server {
    listen 80;
    server_name bulut.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name bulut.example.com;
    
    # ... SSL Cert Config ...

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

## 3. Deployment Checklist
- [ ] `DEPLOY_ENV=PROD` set.
- [ ] `TEZAVER_OPS_TOKEN` is strong and stored securely.
- [ ] `ALLOWED_HOSTS` matches your domain.
- [ ] SSL/TLS enabled via Proxy.
- [ ] Database path is persistent (mounted volume).
