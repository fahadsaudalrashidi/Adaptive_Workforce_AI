"""
AWI RBAC Role & Permission Taxonomy — Phase 30D (trimmed, Phase 34.5).

Defines the role enum and capability→role permission matrix used by the
real, live authentication system (backend/core/local_auth.py +
backend/api/auth_routes.py + backend/core/security_middleware.py).

Phase 34.5 history note: this file originally also shipped a second,
dormant session-management subsystem (AWIUser/AWISession dataclasses, a
credential-less AuthSessionManager, ensure_local_admin_user(), and a
3-table SQLite schema — awi_users/awi_sessions/awi_auth_audit — sharing
data/awi_auth.db with the real auth system). That subsystem was a Phase 30D
scaffold explicitly written as a placeholder ahead of Phase 31 SSO work; it
had NO credential check of any kind (create_local_session() accepted any
user_id with no password), was never imported by any live application
code (only by tests), and never actually wrote its 3 tables to disk in
this deployment. Keeping unused, credential-less "session" code sharing a
database file with the real auth system is a data-integrity and security
footgun with no offsetting benefit, so it was removed rather than wired
in — local_auth.py's LocalAuthManager is the real, tested, shipped
session/credential system and remains the only one. See
PHASE_4_MODULES_REPORT.md for the before/after trace.
"""

from __future__ import annotations

from enum import Enum


# ── RBAC Roles ────────────────────────────────────────────────────────────────

class AWIRole(str, Enum):
    """AWI platform roles. Enforced via security_middleware.py."""
    CHRO          = "chro"           # Full access — all reports, exports, admin
    EXECUTIVE     = "executive"      # Read-only dashboards + board reports
    HR_MANAGER    = "hr_manager"     # Analysis + employee table + exports
    HR_ANALYST    = "hr_analyst"     # Analysis + theory panel, no PII export
    AUDITOR       = "auditor"        # Read-only audit log + governance panel
    SYSTEM_ADMIN  = "system_admin"   # Tenant management + system config


# ── Permission matrix ─────────────────────────────────────────────────────────
# Maps capability → roles allowed to perform it.
# Roles are ordered by privilege (CHRO > EXECUTIVE > HR_MANAGER > HR_ANALYST > AUDITOR > SYSTEM_ADMIN).

PERMISSION_MATRIX: dict[str, list[AWIRole]] = {
    "upload_data":           [AWIRole.CHRO, AWIRole.HR_MANAGER, AWIRole.HR_ANALYST],
    "run_analysis":          [AWIRole.CHRO, AWIRole.HR_MANAGER, AWIRole.HR_ANALYST],
    "view_employee_table":   [AWIRole.CHRO, AWIRole.HR_MANAGER],
    "export_csv":            [AWIRole.CHRO, AWIRole.HR_MANAGER],
    "export_pdf_report":     [AWIRole.CHRO, AWIRole.HR_MANAGER, AWIRole.EXECUTIVE],
    "view_executive_dashboard": [AWIRole.CHRO, AWIRole.HR_MANAGER, AWIRole.EXECUTIVE],
    "view_governance_panel": [AWIRole.CHRO, AWIRole.HR_MANAGER, AWIRole.HR_ANALYST, AWIRole.AUDITOR],
    "view_audit_log":        [AWIRole.CHRO, AWIRole.AUDITOR, AWIRole.SYSTEM_ADMIN],
    "manage_tenants":        [AWIRole.SYSTEM_ADMIN],
    "configure_system":      [AWIRole.CHRO, AWIRole.SYSTEM_ADMIN],
}
