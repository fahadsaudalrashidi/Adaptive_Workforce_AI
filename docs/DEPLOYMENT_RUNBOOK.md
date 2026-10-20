# Deployment Runbook — Phase 7

**Document Type:** Operational Runbook  
**Phase:** 7 — Production SaaS Core & Enterprise Deployment Hardening  
**Date:** 2026-05-20  
**Status:** Draft — Requires Infrastructure Review Before First Live Deployment  
**Audience:** Platform Engineer, DevOps, Saudi-Certified Data Center Operator

---

## 1. Purpose

This runbook provides step-by-step instructions for deploying the Adaptive Workforce AI platform in a local development environment using Docker Compose. It also documents the infrastructure requirements and change controls that must be completed before any live customer or Saudi production deployment.

---

## 2. Prerequisites

### 2.1 Local Development Prerequisites

- Docker Desktop 4.x or later (Windows, macOS, or Linux)
- Docker Compose v2 (included with Docker Desktop)
- Python 3.11+ (for running tests outside Docker)
- Git

### 2.2 Required Before Live Deployment

The following infrastructure components are NOT provisioned in this runbook. They must be configured by your infrastructure team:

| Component | Requirement |
|-----------|-------------|
| Saudi data center | For PDPL compliance, all data must be stored in KSA unless SDAIA cross-border approval obtained |
| PostgreSQL 15+ | Audit log persistence and tenant registry |
| Redis 7+ | Job queue for async training jobs |
| Secrets manager | AWS Secrets Manager / Azure Key Vault / HashiCorp Vault for JWT keys and DB passwords |
| TLS termination | HTTPS-only in production; TLS must terminate at load balancer or reverse proxy |
| Load balancer | For multiple API workers; sticky sessions not required (stateless API) |
| Object storage | S3-compatible storage with tenant-scoped prefixes and IAM policies |

---

## 3. Local Development Deployment

### 3.1 Clone and Configure

```powershell
# Clone repository
git clone <repository-url>
cd Adaptive_Workforce_AI

# Copy environment template
Copy-Item .env.example .env
# Edit .env with your local settings (no real secrets needed for development)
```

### 3.2 Run the Test Suite

Before deploying, verify all tests pass:

```powershell
py -m pytest tests/ -q --tb=short
```

Expected output: `442 passed, 0 failed`

If any tests fail, do NOT proceed with deployment. Investigate and fix failures first.

### 3.3 Build the Docker Image

```powershell
docker build -t adaptive-workforce-ai .
```

The build:
1. Uses `python:3.11-slim` as base
2. Installs system dependencies (`build-essential`)
3. Creates non-root user `appuser`
4. Installs Python dependencies from `requirements.txt`
5. Copies application code (owned by `appuser`)
6. Creates data directories
7. Sets healthcheck

### 3.4 Start the Stack

```powershell
docker-compose up -d
```

This starts:
- `adaptive_workforce_api` container on port 8000

Optional services (commented out by default in `docker-compose.yml`):
- Streamlit demo interface (port 8501)
- PostgreSQL (port 5432)
- Redis (port 6379)

### 3.5 Verify Startup

```powershell
# Check container is running
docker ps

# Check API health
Invoke-WebRequest -Uri http://localhost:8000/health

# Check container logs for governance lock verification
docker logs adaptive_workforce_api | Select-String "governance"
```

Expected: container is running, health endpoint returns 200, governance locks confirmed in startup logs.

### 3.6 Stop the Stack

```powershell
docker-compose down
```

To also remove data volumes (destructive):
```powershell
docker-compose down -v
```

---

## 4. First-Run Checklist

Before serving any real tenant data, complete the following:

### 4.1 Governance Verification

- [ ] Run `py -m pytest tests/ -q` — all 442+ tests pass
- [ ] `assert_production_governance_locks()` passes at startup (confirmed in logs)
- [ ] `DEBUG = False` confirmed in production settings
- [ ] `EMPLOYEE_LEVEL_OUTPUT_ENABLED = False` confirmed

### 4.2 Security

- [ ] JWT authentication implemented (placeholder replaced with production implementation)
- [ ] TLS certificate installed and HTTPS enforced (HTTP requests redirected)
- [ ] Secrets stored in secrets manager (not in `.env` file in production)
- [ ] Non-root `appuser` confirmed in running container (`docker exec adaptive_workforce_api whoami`)
- [ ] Penetration test completed by security team

### 4.3 Compliance

- [ ] Data center location confirmed in KSA (or SDAIA cross-border transfer approval obtained)
- [ ] Data Processing Agreement (DPA) signed with customer covering PDPL requirements
- [ ] Data Processing Impact Assessment (DPIA) completed
- [ ] PDPL data subject notification mechanism in place

### 4.4 Data

- [ ] PostgreSQL provisioned and connected for audit log persistence
- [ ] Backup and recovery tested for audit log database
- [ ] Data retention policy configured (minimum 7 years for model artifacts)

---

## 5. Upgrading the Platform

### 5.1 Before Each Upgrade

```powershell
# Run full test suite against new code
py -m pytest tests/ -q --tb=short

# Review governance lock constants for any changes
git diff HEAD~1 config/production_settings.py
```

If governance lock constants changed, require formal review before deploying.

### 5.2 Rolling Update Procedure (No Downtime)

1. Build new image: `docker build -t adaptive-workforce-ai:new .`
2. Update `docker-compose.yml` to reference new image tag
3. Run `docker-compose up -d --no-deps api` (restarts API container only)
4. Monitor health: `docker logs -f adaptive_workforce_api`
5. Verify: `Invoke-WebRequest -Uri http://localhost:8000/health`
6. If failed: roll back with `docker-compose up -d --no-deps api` on previous image tag

### 5.3 Database Migrations

Not currently applicable (in-memory stores in Phase 7). When persistent storage is added, migrations must:
- Be reviewed before deployment
- Be reversible (rollback script required)
- Not drop audit log tables or tenant data
- Be tested against a copy of production data first

---

## 6. Healthcheck

The Docker container healthcheck polls `http://localhost:8000/health` every 30 seconds with a 10-second timeout and 3 retries before declaring unhealthy. The start period is 40 seconds (allows uvicorn to initialize).

If the container enters unhealthy state:
1. `docker logs adaptive_workforce_api` — check for governance lock failures, import errors
2. `docker inspect adaptive_workforce_api | grep Health` — detailed health status
3. Restart: `docker-compose restart api`

---

## 7. Log Access

```powershell
# Live logs
docker logs -f adaptive_workforce_api

# Last 100 lines
docker logs --tail 100 adaptive_workforce_api

# Filter for errors
docker logs adaptive_workforce_api 2>&1 | Select-String "ERROR|CRITICAL"
```

Production logs should be shipped to a centralized log management system (CloudWatch, Azure Monitor, Datadog) — not stored only in the container.

---

## 8. Environment Variable Reference

| Variable | Development Default | Production Required Value |
|----------|--------------------|-----------------------------|
| `ENVIRONMENT` | `development` | `production` |
| `LOG_LEVEL` | `INFO` | `INFO` or `WARNING` |
| `API_PORT` | `8000` | `8000` (or behind load balancer) |
| `API_HOST` | `0.0.0.0` | `0.0.0.0` |
| `ARTIFACT_STORE_PATH` | `./data/artifacts` | Object storage path |
| `AUDIT_LOG_PATH` | `./data/audit_logs` | PostgreSQL connection |
| `MODEL_STORE_PATH` | `./saved_models` | Object storage path |
| `SAUDI_COMPLIANCE_MODE` | `true` | `true` (never disable) |
| `PDPL_WARNING_ENABLED` | `true` | `true` (never disable) |
| `JWT_SECRET_KEY` | Not set | Required — from secrets manager |

---

## 9. Incident Response

### 9.1 Suspected Cross-Tenant Data Leakage

1. Immediately stop the API container: `docker-compose stop api`
2. Capture logs: `docker logs adaptive_workforce_api > incident_$(Get-Date -Format 'yyyyMMdd_HHmmss').log`
3. Notify legal and compliance team within 72 hours (PDPL Article 33 breach notification requirement)
4. Do not restart until root cause is identified and mitigated
5. Preserve container state for forensics: `docker commit adaptive_workforce_api incident_snapshot`

### 9.2 Governance Lock Failure at Startup

If `assert_production_governance_locks()` raises `RuntimeError`:
1. The application will not start — this is correct behavior
2. Review startup logs to identify which lock failed
3. Check recent changes to `config/production_settings.py`
4. Restore correct lock values and redeploy

### 9.3 PII Detected in Export

If `EVT_PII_DETECTED` audit event fires:
1. The export was blocked by `ExportSafetyValidator` — no data was sent to the caller
2. Review the tenant's dataset for PII fields that should have been removed during onboarding
3. Run the onboarding pipeline again after removing PII columns from the source dataset
4. Log a PDPL incident report if PII reached the export stage from a dataset that passed initial validation

---

## 10. Saudi Deployment Notes

### 10.1 Data Residency

All tenant data must be stored in Saudi Arabia unless SDAIA (Saudi Data & Artificial Intelligence Authority) cross-border transfer approval has been obtained. This applies to:
- Uploaded datasets (even after processing)
- Trained model artifacts
- Audit logs
- Export packages

The Docker Compose configuration does not enforce data residency — this is an infrastructure and legal requirement.

### 10.2 Nitaqat/Saudization Monitoring

Some customers use this platform to monitor Saudization compliance. If Qiwa platform data is integrated:
- Verify that Qiwa API terms permit third-party processing
- Confirm that Saudization records are covered under the customer's PDPL data processing registration

### 10.3 Arabic Language Support

The platform supports Arabic column names (Mudad payroll format). Ensure the deployment environment uses UTF-8 encoding throughout. Log files, database tables, and API responses must handle Arabic strings correctly.

---

*This runbook covers the Phase 7 Docker deployment. Production deployment requires additional infrastructure, security, and legal steps not in scope for this runbook. Always run the full test suite before deploying.*
