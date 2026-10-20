# AWI Local Deployment Package
## Enterprise On-Premises Installation Guide
**Version:** v2.0.1-enterprise | **Model:** Enterprise License

---

## Overview

AWI is deployed as a self-contained package on the customer's own infrastructure. No internet connection is required after installation. No data leaves the customer's environment.

**Deployment topology:**
```
[Internal User Browsers]
         ↓ HTTPS (TLS)
[nginx reverse proxy] ← Customer manages TLS certificate
         ↓ HTTP (localhost only)
[AWI API Server :8000]   [AWI Frontend :8501]
         ↓                        ↓
[SQLite databases in /opt/awi/data/]
```

---

## System Requirements

### Minimum (Pilot / ≤500 employees)
| Component | Requirement |
|-----------|------------|
| OS | Ubuntu 22.04 LTS / RHEL 9 / Windows Server 2022 |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 20 GB SSD |
| Python | 3.11+ |
| Node.js | 18+ (for frontend build only) |

### Recommended (Production / ≤5,000 employees)
| Component | Requirement |
|-----------|------------|
| CPU | 8 vCPU |
| RAM | 16 GB |
| Disk | 100 GB SSD |
| Network | Isolated VLAN, internal access only |

---

## Installation Steps

### Step 1 — Unpack Deployment Archive

```bash
tar -xzf awi-enterprise-v2.0.1.tar.gz -C /opt/awi
cd /opt/awi
```

### Step 2 — Create Service Account

```bash
# Linux
useradd -r -s /bin/false -d /opt/awi awi-service
chown -R awi-service:awi-service /opt/awi
chmod 700 /opt/awi/data
```

### Step 3 — Install Python Dependencies

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --no-index --find-links ./wheels -r requirements.txt
```

> **Air-gapped environments:** Pre-download all wheels using `pip download -r requirements.txt -d wheels/` on an internet-connected machine, then copy the `wheels/` directory into the deployment archive.

### Step 4 — Set Environment Variables

Create `/opt/awi/.env` (owner: `awi-service`, mode: `600`):

```env
# REQUIRED on first boot — will be cleared after bootstrap
AWI_ADMIN_BOOTSTRAP_PASSWORD=<strong-initial-password>

# Set to restrict API access to specific internal hosts
AWI_CORS_ORIGINS=http://awi.internal,https://awi.internal

# Set to false ONLY during integration testing
AWI_AUTH_ENFORCED=true
```

> **Security note:** `AWI_ADMIN_BOOTSTRAP_PASSWORD` creates the initial `admin` account on first boot. The admin must change this password on first login. Remove the variable from `.env` after first boot.

### Step 5 — Build Frontend (one-time)

```bash
cd /opt/awi/executive-ui
npm ci --prefer-offline
npm run build
```

The built assets are output to `executive-ui/dist/` and served statically by the API.

### Step 6 — Start Services

**Option A — systemd (recommended for production)**

```ini
# /etc/systemd/system/awi-api.service
[Unit]
Description=AWI Enterprise API
After=network.target

[Service]
Type=simple
User=awi-service
WorkingDirectory=/opt/awi
EnvironmentFile=/opt/awi/.env
ExecStart=/opt/awi/venv/bin/uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable awi-api
systemctl start awi-api
```

**Option B — Docker (optional)**

```bash
docker build -t awi-enterprise:2.0.1 .
docker run -d \
  --name awi \
  -p 127.0.0.1:8000:8000 \
  -v /opt/awi/data:/app/data \
  --env-file /opt/awi/.env \
  awi-enterprise:2.0.1
```

### Step 7 — Configure nginx (TLS termination)

```nginx
server {
    listen 443 ssl;
    server_name awi.internal;

    ssl_certificate     /etc/ssl/awi/cert.pem;
    ssl_certificate_key /etc/ssl/awi/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    # API
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   Authorization $http_authorization;
        client_max_body_size 50M;
    }

    # Frontend
    location / {
        root   /opt/awi/executive-ui/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

### Step 8 — First-Boot Admin Setup

```bash
# Bootstrap the admin account (idempotent — safe to run again)
curl -X POST "http://127.0.0.1:8000/api/auth/bootstrap?initial_password=<strong-password>"

# Verify
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<strong-password>"}'
```

The admin account has `must_change_password: true`. The admin must set a new password before using the system.

---

## Post-Installation Checklist

- [ ] Admin account bootstrapped
- [ ] Admin password changed from initial
- [ ] nginx TLS configured with valid certificate
- [ ] Port 8000 blocked at firewall (only nginx exposed)
- [ ] `AWI_ADMIN_BOOTSTRAP_PASSWORD` removed from `.env`
- [ ] `data/` directory permissions set to `awi-service` only
- [ ] SQLite backup script scheduled (see Backup section)
- [ ] Log rotation configured for systemd journal

---

## Data Directory Structure

```
/opt/awi/data/
  ├── awi_auth.db          # User accounts, tokens, audit log
  ├── awi_secret.key       # JWT signing secret (chmod 600)
  ├── awi_analysis.db      # Analysis persistence (Phase 21)
  ├── awi_history.db       # Historical snapshots (Phase 30E)
  ├── awi_tenants.db       # Tenant manager (Phase 30C)
  └── snapshots/           # Workforce trend snapshots
```

> **Critical:** Never delete `awi_secret.key`. This would invalidate all existing sessions and require all users to re-login. If the key is lost, delete it and restart the service — a new key will be generated and all tokens will be automatically invalidated.

---

## Backup Procedure

```bash
#!/bin/bash
# /opt/awi/scripts/backup.sh — run via cron daily at 02:00
BACKUP_DIR="/opt/awi/backups/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# SQLite online backup (safe during operation — uses WAL)
for db in auth analysis history tenants; do
  sqlite3 /opt/awi/data/awi_${db}.db ".backup '$BACKUP_DIR/awi_${db}.db'"
done

# Retain 30 days of backups
find /opt/awi/backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
```

---

## Upgrade Procedure

```bash
# 1. Stop service
systemctl stop awi-api

# 2. Backup databases
/opt/awi/scripts/backup.sh

# 3. Extract new version
tar -xzf awi-enterprise-v2.x.x.tar.gz -C /tmp/awi-new

# 4. Replace code only (preserve data/)
rsync -av --exclude=data/ /tmp/awi-new/ /opt/awi/

# 5. Reinstall dependencies if requirements.txt changed
/opt/awi/venv/bin/pip install -r /opt/awi/requirements.txt

# 6. Rebuild frontend
cd /opt/awi/executive-ui && npm ci && npm run build

# 7. Restart service
systemctl start awi-api
```

---

## Firewall Rules

```bash
# Allow only from internal VLAN (example: 10.100.0.0/24)
ufw allow from 10.100.0.0/24 to any port 443
ufw deny 8000   # block direct API access from outside
ufw deny 8501   # block direct Streamlit access from outside
ufw enable
```

---

## Key Rotation

JWT key rotation invalidates all active sessions. Schedule during a maintenance window.

```bash
# 1. Delete the existing key
rm /opt/awi/data/awi_secret.key

# 2. Restart — new key generated automatically
systemctl restart awi-api

# 3. Inform users: all sessions have been invalidated
```

Recommended rotation schedule: annually, or immediately if the key file is believed compromised.

---

*AWI Enterprise Workforce Intelligence Platform v2.0.1 | Confidential — Customer Deployment*
