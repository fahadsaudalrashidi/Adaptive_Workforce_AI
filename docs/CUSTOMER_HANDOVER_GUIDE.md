# AWI Customer Handover Guide
## Enterprise On-Premises Deployment — IT Administrator Reference
**Version:** v2.0.1-enterprise | **Support Contact:** implementation@awi-platform.com

---

## What You Are Receiving

AWI Enterprise Workforce Intelligence Platform is delivered as a **fully self-contained software package**. You receive:

1. **Source package** (or Docker image) — the full AWI application
2. **This handover guide** — IT administrator reference
3. **Deployment package** (`LOCAL_DEPLOYMENT_PACKAGE.md`) — step-by-step installation
4. **License key** — tied to your organisation name (embedded in config)
5. **Training session** — 4-hour virtual session with your HR and IT leads

**What you do NOT receive:**
- Access to a shared cloud environment
- Any service that phones home
- Any dependency on Anthropic or AWI vendor infrastructure after installation

---

## Pre-Deployment Checklist

### Infrastructure (IT)
- [ ] Server provisioned (8 vCPU, 16 GB RAM, 100 GB SSD)
- [ ] Ubuntu 22.04 LTS or RHEL 9 installed
- [ ] Python 3.11+ installed
- [ ] nginx installed
- [ ] TLS certificate obtained (internal CA acceptable for air-gapped)
- [ ] Internal DNS entry created (e.g., `awi.internal.yourorg.com`)
- [ ] Firewall rules prepared (allow port 443 from user VLAN)

### HR / Platform Owner
- [ ] Identified CHRO sponsor
- [ ] Identified System Administrator (1-2 people who will manage accounts)
- [ ] Identified initial user list and roles
- [ ] Prepared 3 months of workforce data in Excel/CSV format
- [ ] Data cleared by legal/DPO for local processing

---

## User Roles Reference

| Role | Who Holds This | What They Can Do |
|------|----------------|-----------------|
| `system_admin` | IT Admin / HR Ops lead | Create/deactivate users, reset passwords, view audit log, unlock accounts |
| `chro` | CHRO | Full platform access, configure system, view all dashboards |
| `executive` | CEO/CFO | View executive dashboard, download board reports |
| `hr_manager` | HR Business Partners | Run analyses, view employee risk table, export CSV/PDF |
| `hr_analyst` | HR Analysts | Upload data, run analyses, view governance panel |
| `auditor` | Internal Audit / Compliance | Read-only: view governance panel, view audit log |

---

## Day-1 Setup (System Administrator)

### 1. Bootstrap the admin account

On first launch, call the bootstrap endpoint once:

```bash
curl -X POST "https://awi.internal/api/auth/bootstrap?initial_password=<choose-strong-password>"
```

The system creates user `admin` with role `system_admin`. The `must_change_password` flag is set — the admin must change the password on first login.

### 2. Log in and change password

Open `https://awi.internal` in your browser. Log in as `admin` and change the password when prompted.

### 3. Create user accounts

Navigate to **Settings → User Management** (or use the API directly):

```bash
# Example: create an HR analyst
curl -X POST https://awi.internal/api/auth/users \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "ahmed.al-rashidi",
    "display_name": "Ahmed Al-Rashidi",
    "email": "ahmed.al-rashidi@yourorg.com",
    "role": "hr_analyst",
    "initial_password": "Temp@2025ChangeMe"
  }'
```

All new users have `must_change_password: true` by default.

### 4. Communicate credentials

Send each user their username and initial password through a secure internal channel (not email). They must change it on first login.

---

## Password Policy

All passwords must meet:
- Minimum 10 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character (`!@#$%^&*` etc.)

**Account lockout:** 5 consecutive failures within 15 minutes → account locked for 15 minutes. System Admin can unlock manually via `POST /api/auth/users/{username}/unlock`.

---

## Data Preparation Guide

### Supported Formats
- Excel (.xlsx, .xls)
- CSV (.csv)
- Parquet (.parquet)

### Minimum Required Columns

At minimum, your workforce file should contain:

| Column | Example |
|--------|---------|
| Employee ID | EMP001234 |
| Department | Finance |
| Tenure (years) | 4.5 |
| Role/Job Title | Senior Analyst |
| Performance rating | 3 (1–5 scale) |
| Absenteeism (days/year) | 12 |

AWI's semantic mapper will automatically detect column names in Arabic or English.

### Data Privacy
- Remove any columns not relevant to workforce analysis (national ID, home address, personal phone)
- AWI processes data in-memory during analysis; results are persisted to your local database
- No data is transmitted outside your infrastructure

---

## Ongoing Administration

### Adding Users
```bash
POST /api/auth/users   (requires system_admin token)
```

### Deactivating Users (offboarding)
```bash
DELETE /api/auth/users/{user_id}   (soft delete — account deactivated, data retained for audit)
```

### Resetting a Forgotten Password
```bash
POST /api/auth/users/{user_id}/reset-password
  body: {"new_password": "...", "force_change": true}
```

### Viewing the Security Audit Log
```bash
GET /api/auth/audit-log?limit=100   (requires auditor or higher)
```

### Scheduled Backups
The deployment script installs a cron job at `/opt/awi/scripts/backup.sh` that runs nightly at 02:00 and retains 30 days of database backups in `/opt/awi/backups/`.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Invalid or expired token" | Token expired (8h TTL) | Log in again |
| "Account temporarily locked" | 5 failed login attempts | Wait 15 min or admin unlocks |
| Analysis page shows 0 results | File format issue | Check column headers; use CSV |
| API returns 500 | Service crashed | `systemctl status awi-api`; check `journalctl -u awi-api -n 50` |
| "CORS error" in browser | Accessing from unexpected host | Add origin to `AWI_CORS_ORIGINS` env var |
| Frontend blank / 404 | Frontend not built | Run `cd executive-ui && npm run build` |

---

## Support Escalation

| Level | Contact | SLA |
|-------|---------|-----|
| L1 — Usage questions | Internal HR Ops | Same day |
| L2 — Config/deployment | IT Admin (this guide) | Same day |
| L3 — Software defect | implementation@awi-platform.com | 48 hours |
| Emergency (data loss) | +966-XX-XXX-XXXX | 4 hours |

Include in all support tickets:
1. AWI version (`GET /api/v1/status`)
2. Error message + timestamp
3. OS and deployment type (systemd / Docker)
4. Anonymised example data file if analysis-related

---

## Frequently Asked Questions

**Q: Does AWI call home or phone the vendor?**
No. The application makes no external network calls. All processing is local. You can verify with `tcpdump` or network monitoring.

**Q: Can we run AWI on an air-gapped network?**
Yes. After installation, AWI has no runtime internet dependency.

**Q: How do we update AWI?**
You receive new deployment packages from the vendor. Run the upgrade procedure in `LOCAL_DEPLOYMENT_PACKAGE.md`. Database schema is upgraded automatically on first start.

**Q: Where is employee data stored?**
In SQLite databases under `/opt/awi/data/`. These are plain files on your server. Secure them with OS-level permissions.

**Q: Can multiple organisations share one AWI deployment?**
No. Each organisation receives their own deployment. The multi-tenant architecture supports future segmentation within a single organisation (e.g., multiple business units), but cross-organisation sharing is not supported.

---

*AWI Enterprise Workforce Intelligence Platform v2.0.1 | Confidential — Not for Distribution*
