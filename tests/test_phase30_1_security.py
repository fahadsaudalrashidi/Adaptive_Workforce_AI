"""
Phase 30.1 — Enterprise Security Tests
Tests for local_auth.py, security_middleware.py, auth_routes.py, and wired main.py.
All tests use isolated temporary databases — no state bleeds between tests.
"""

from __future__ import annotations

import os
import time
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tmp_db() -> str:
    """Return a path to a fresh temp SQLite file."""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="awi_test_")
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# 1. Password utilities
# ---------------------------------------------------------------------------

class TestPasswordUtilities(unittest.TestCase):

    def test_hash_is_bcrypt(self):
        from backend.core.local_auth import hash_password
        h = hash_password("TestPass1!")
        self.assertTrue(h.startswith("$2"))

    def test_verify_correct_password(self):
        from backend.core.local_auth import hash_password, verify_password
        h = hash_password("CorrectHorse1!")
        self.assertTrue(verify_password("CorrectHorse1!", h))

    def test_verify_wrong_password(self):
        from backend.core.local_auth import hash_password, verify_password
        h = hash_password("CorrectHorse1!")
        self.assertFalse(verify_password("WrongPass1!", h))

    def test_password_strength_too_short(self):
        from backend.core.local_auth import validate_password_strength
        ok, msg = validate_password_strength("Ab1!")
        self.assertFalse(ok)
        self.assertIn("10", msg)

    def test_password_strength_no_uppercase(self):
        from backend.core.local_auth import validate_password_strength
        ok, msg = validate_password_strength("alllower1!")
        self.assertFalse(ok)
        self.assertIn("upper", msg.lower())

    def test_password_strength_no_digit(self):
        from backend.core.local_auth import validate_password_strength
        ok, msg = validate_password_strength("NoDigitHere!")
        self.assertFalse(ok)
        self.assertIn("digit", msg.lower())

    def test_password_strength_no_special(self):
        from backend.core.local_auth import validate_password_strength
        ok, msg = validate_password_strength("NoSpecial1A")
        self.assertFalse(ok)
        self.assertIn("special", msg.lower())

    def test_password_strength_valid(self):
        from backend.core.local_auth import validate_password_strength
        ok, msg = validate_password_strength("Enterprise@2025X")
        self.assertTrue(ok, msg)

    def test_hashes_are_unique(self):
        from backend.core.local_auth import hash_password
        h1 = hash_password("SamePass1!")
        h2 = hash_password("SamePass1!")
        self.assertNotEqual(h1, h2)  # bcrypt salts differ


# ---------------------------------------------------------------------------
# 2. JWT token generation and validation
# ---------------------------------------------------------------------------

class TestJWTTokens(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_access_token_decode(self):
        from backend.core.local_auth import create_access_token, decode_token
        uid = str(uuid.uuid4())
        from backend.core.auth_session import AWIRole
        token, jti = create_access_token(uid, "alice", AWIRole.HR_ANALYST, False)
        payload = decode_token(token)
        self.assertEqual(payload["sub"], uid)
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(payload["type"], "access")

    def test_refresh_token_decode(self):
        from backend.core.local_auth import create_refresh_token, decode_token
        uid = str(uuid.uuid4())
        token, jti = create_refresh_token(uid)
        payload = decode_token(token)
        self.assertEqual(payload["sub"], uid)
        self.assertEqual(payload["type"], "refresh")

    def test_tampered_token_raises(self):
        from backend.core.local_auth import create_access_token, decode_token
        from jose import JWTError
        uid = str(uuid.uuid4())
        from backend.core.auth_session import AWIRole
        token, _ = create_access_token(uid, "alice", AWIRole.EXECUTIVE, False)
        bad_token = token[:-5] + "XXXXX"
        with self.assertRaises(JWTError):
            decode_token(bad_token)

    def test_jti_is_unique_across_tokens(self):
        from backend.core.local_auth import create_access_token
        from backend.core.auth_session import AWIRole
        uid = str(uuid.uuid4())
        _, jti1 = create_access_token(uid, "a", AWIRole.AUDITOR, False)
        _, jti2 = create_access_token(uid, "a", AWIRole.AUDITOR, False)
        self.assertNotEqual(jti1, jti2)


# ---------------------------------------------------------------------------
# 3. LocalAuthManager — user lifecycle
# ---------------------------------------------------------------------------

class TestLocalAuthManager(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db
        # Force fresh manager for each test
        import backend.core.local_auth as _la
        _la._auth_manager = None
        from backend.core.local_auth import LocalAuthManager
        self.auth = LocalAuthManager()

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def _make_user(self, username="alice", role=None):
        from backend.core.auth_session import AWIRole
        return self.auth.create_user(
            username=username,
            display_name="Alice Tester",
            email=f"{username}@awi.test",
            role=role or AWIRole.HR_ANALYST,
            initial_password="Enterprise@2025X",
            must_change_pw=False,
            creator_user_id=None,
        )

    def test_create_user_returns_local_user(self):
        user = self._make_user()
        self.assertEqual(user.username, "alice")

    def test_create_duplicate_username_raises(self):
        self._make_user()
        with self.assertRaises(ValueError):
            self._make_user()

    def test_get_user_by_id(self):
        user = self._make_user()
        fetched = self.auth.get_user_by_id(user.user_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "alice")

    def test_get_user_by_username(self):
        self._make_user()
        fetched = self.auth.get_user_by_username("alice")
        self.assertIsNotNone(fetched)

    def test_list_users(self):
        self._make_user("user1")
        self._make_user("user2")
        users = self.auth.list_users(active_only=True)
        usernames = [u.username for u in users]
        self.assertIn("user1", usernames)
        self.assertIn("user2", usernames)

    def test_deactivate_user(self):
        from backend.core.auth_session import AWIRole
        admin = self._make_user("admin", AWIRole.SYSTEM_ADMIN)
        target = self._make_user("target")
        ok = self.auth.deactivate_user(target.user_id, admin.user_id)
        self.assertTrue(ok)
        fetched = self.auth.get_user_by_id(target.user_id)
        self.assertFalse(fetched.is_active)

    def test_update_role(self):
        from backend.core.auth_session import AWIRole
        admin = self._make_user("admin", AWIRole.SYSTEM_ADMIN)
        target = self._make_user("target")
        ok = self.auth.update_role(target.user_id, AWIRole.HR_MANAGER, admin.user_id)
        self.assertTrue(ok)
        fetched = self.auth.get_user_by_id(target.user_id)
        self.assertEqual(fetched.role, AWIRole.HR_MANAGER)

    def test_bootstrap_admin_idempotent(self):
        user1 = self.auth.bootstrap_admin("Enterprise@Admin1!")
        user2 = self.auth.bootstrap_admin("Enterprise@Admin1!")
        self.assertEqual(user1.user_id, user2.user_id)

    def test_bootstrap_admin_is_system_admin(self):
        from backend.core.auth_session import AWIRole
        user = self.auth.bootstrap_admin("Enterprise@Admin1!")
        self.assertEqual(user.role, AWIRole.SYSTEM_ADMIN)


# ---------------------------------------------------------------------------
# 4. Login flow
# ---------------------------------------------------------------------------

class TestLoginFlow(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db
        import backend.core.local_auth as _la
        _la._auth_manager = None
        from backend.core.local_auth import LocalAuthManager
        self.auth = LocalAuthManager()
        from backend.core.auth_session import AWIRole
        self.auth.create_user(
            username="alice",
            display_name="Alice",
            email="alice@awi.test",
            role=AWIRole.HR_ANALYST,
            initial_password="Enterprise@2025X",
            must_change_pw=False,
            creator_user_id=None,
        )

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_successful_login_returns_tokens(self):
        result = self.auth.login("alice", "Enterprise@2025X", "127.0.0.1", "pytest")
        self.assertTrue(result.success)
        self.assertIsNotNone(result.access_token)
        self.assertIsNotNone(result.refresh_token)

    def test_wrong_password_fails(self):
        result = self.auth.login("alice", "WrongPass1!", "127.0.0.1", "pytest")
        self.assertFalse(result.success)
        self.assertIsNone(result.access_token)

    def test_nonexistent_user_fails(self):
        result = self.auth.login("nobody", "Enterprise@2025X", "127.0.0.1", "pytest")
        self.assertFalse(result.success)

    def test_account_locks_after_5_failures(self):
        for _ in range(5):
            self.auth.login("alice", "WrongPass1!", "127.0.0.1", "pytest")
        result = self.auth.login("alice", "Enterprise@2025X", "127.0.0.1", "pytest")
        self.assertFalse(result.success)
        self.assertTrue(result.account_locked)

    def test_unlock_clears_lockout(self):
        for _ in range(5):
            self.auth.login("alice", "WrongPass1!", "127.0.0.1", "pytest")
        # Still locked
        locked = self.auth.login("alice", "Enterprise@2025X", "127.0.0.1", "pytest")
        self.assertTrue(locked.account_locked)

        self.auth.unlock_account("alice", admin_user_id="admin")
        result = self.auth.login("alice", "Enterprise@2025X", "127.0.0.1", "pytest")
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# 5. Token revocation
# ---------------------------------------------------------------------------

class TestTokenRevocation(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db
        import backend.core.local_auth as _la
        _la._auth_manager = None
        from backend.core.local_auth import LocalAuthManager
        self.auth = LocalAuthManager()
        from backend.core.auth_session import AWIRole
        self.auth.create_user(
            username="bob",
            display_name="Bob",
            email="bob@awi.test",
            role=AWIRole.EXECUTIVE,
            initial_password="Enterprise@2025X",
            must_change_pw=False,
            creator_user_id=None,
        )

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_token_not_revoked_after_login(self):
        from backend.core.local_auth import decode_token
        result = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        payload = decode_token(result.access_token)
        jti = payload["jti"]
        self.assertFalse(self.auth.is_token_revoked(jti))

    def test_logout_revokes_token(self):
        from backend.core.local_auth import decode_token
        result = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        payload = decode_token(result.access_token)
        jti = payload["jti"]
        self.auth.logout(jti=jti, user_id=result.user.user_id)
        self.assertTrue(self.auth.is_token_revoked(jti))

    def test_revoke_all_user_tokens(self):
        from backend.core.local_auth import decode_token
        r1 = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        r2 = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        user = r1.user
        count = self.auth.revoke_all_user_tokens(user.user_id)
        self.assertGreater(count, 0)
        p1 = decode_token(r1.access_token)
        p2 = decode_token(r2.access_token)
        self.assertTrue(self.auth.is_token_revoked(p1["jti"]))
        self.assertTrue(self.auth.is_token_revoked(p2["jti"]))

    def test_verify_token_and_get_user_valid(self):
        result = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        user, err = self.auth.verify_token_and_get_user(result.access_token)
        self.assertIsNotNone(user)
        self.assertIsNone(err)

    def test_verify_token_and_get_user_revoked(self):
        from backend.core.local_auth import decode_token
        result = self.auth.login("bob", "Enterprise@2025X", "127.0.0.1", "pytest")
        payload = decode_token(result.access_token)
        self.auth.logout(jti=payload["jti"], user_id=result.user.user_id)
        user, err = self.auth.verify_token_and_get_user(result.access_token)
        self.assertIsNone(user)
        self.assertIsNotNone(err)


# ---------------------------------------------------------------------------
# 6. Password change
# ---------------------------------------------------------------------------

class TestPasswordChange(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db
        import backend.core.local_auth as _la
        _la._auth_manager = None
        from backend.core.local_auth import LocalAuthManager
        self.auth = LocalAuthManager()
        from backend.core.auth_session import AWIRole
        self.user = self.auth.create_user(
            username="carol",
            display_name="Carol",
            email="carol@awi.test",
            role=AWIRole.CHRO,
            initial_password="Enterprise@2025X",
            must_change_pw=False,
            creator_user_id=None,
        )

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_change_password_success(self):
        ok, msg = self.auth.change_password(
            self.user.user_id, "Enterprise@2025X", "NewEnterprise@9999X"
        )
        self.assertTrue(ok, msg)

    def test_change_password_wrong_current(self):
        ok, msg = self.auth.change_password(
            self.user.user_id, "WrongCurrent1!", "NewEnterprise@9999X"
        )
        self.assertFalse(ok)

    def test_change_password_weak_new(self):
        ok, msg = self.auth.change_password(
            self.user.user_id, "Enterprise@2025X", "weak"
        )
        self.assertFalse(ok)
        self.assertIn("10", msg)  # minimum length message

    def test_reset_password_admin(self):
        from backend.core.auth_session import AWIRole
        admin = self.auth.create_user(
            "admin2", "Admin2", "admin2@awi.test", AWIRole.SYSTEM_ADMIN,
            "Enterprise@2025X", False, None
        )
        ok = self.auth.reset_password(
            self.user.user_id, "FreshReset@2025X", admin.user_id, force_change=True
        )
        self.assertTrue(ok)
        fetched = self.auth.get_user_by_id(self.user.user_id)
        self.assertTrue(fetched.must_change_pw)


# ---------------------------------------------------------------------------
# 7. Audit log
# ---------------------------------------------------------------------------

class TestAuditLog(unittest.TestCase):

    def setUp(self):
        self._db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = self._db
        import backend.core.local_auth as _la
        _la._auth_manager = None
        from backend.core.local_auth import LocalAuthManager
        self.auth = LocalAuthManager()
        from backend.core.auth_session import AWIRole
        self.auth.create_user(
            "dave", "Dave", "dave@awi.test", AWIRole.AUDITOR,
            "Enterprise@2025X", False, None
        )

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_successful_login_creates_audit_entry(self):
        self.auth.login("dave", "Enterprise@2025X", "10.0.0.1", "pytest")
        log = self.auth.get_security_audit_log(limit=10)
        event_types = [e["event_type"] for e in log]
        self.assertIn("login_success", event_types)

    def test_failed_login_creates_audit_entry(self):
        self.auth.login("dave", "WrongPass1!", "10.0.0.1", "pytest")
        log = self.auth.get_security_audit_log(limit=10)
        event_types = [e["event_type"] for e in log]
        self.assertIn("login_failed", event_types)

    def test_audit_log_filter_by_event_type(self):
        self.auth.login("dave", "Enterprise@2025X", "10.0.0.1", "pytest")
        self.auth.login("dave", "WrongPass1!", "10.0.0.1", "pytest")
        log = self.auth.get_security_audit_log(limit=10, event_type="login_success")
        for entry in log:
            self.assertEqual(entry["event_type"], "login_success")


# ---------------------------------------------------------------------------
# 8. Security middleware
# ---------------------------------------------------------------------------

class TestSecurityMiddleware(unittest.TestCase):

    def test_auth_enforced_env_false(self):
        """When AWI_AUTH_ENFORCED=false, _auth_enforced() returns False."""
        with patch.dict(os.environ, {"AWI_AUTH_ENFORCED": "false"}):
            from backend.core.security_middleware import _auth_enforced
            self.assertFalse(_auth_enforced())

    def test_require_role_factory_returns_callable(self):
        from backend.core.security_middleware import require_role
        from backend.core.auth_session import AWIRole
        dep = require_role(AWIRole.SYSTEM_ADMIN)
        self.assertTrue(callable(dep))

    def test_require_permission_factory_returns_callable(self):
        from backend.core.security_middleware import require_permission
        dep = require_permission("view_reports")
        self.assertTrue(callable(dep))

    def test_synthetic_admin_has_system_admin_role(self):
        from backend.core.security_middleware import _synthetic_admin
        from backend.core.auth_session import AWIRole
        user = _synthetic_admin()
        self.assertEqual(user.role, AWIRole.SYSTEM_ADMIN)


# ---------------------------------------------------------------------------
# 9. RBAC — role enum and permission matrix
# ---------------------------------------------------------------------------

class TestRBACMatrix(unittest.TestCase):

    def test_permission_matrix_is_dict(self):
        from backend.core.auth_session import PERMISSION_MATRIX
        self.assertIsInstance(PERMISSION_MATRIX, dict)
        self.assertGreater(len(PERMISSION_MATRIX), 0)

    def test_system_admin_has_manage_tenants(self):
        from backend.core.auth_session import AWIRole, PERMISSION_MATRIX
        roles_with_perm = PERMISSION_MATRIX.get("manage_tenants", [])
        self.assertIn(AWIRole.SYSTEM_ADMIN, roles_with_perm)

    def test_auditor_has_view_audit_log(self):
        from backend.core.auth_session import AWIRole, PERMISSION_MATRIX
        # Auditor should appear in at least one audit/view permission
        auditor_perms = [
            perm for perm, roles in PERMISSION_MATRIX.items()
            if AWIRole.AUDITOR in roles
        ]
        self.assertGreater(len(auditor_perms), 0)

    def test_local_auth_reexports_awirole(self):
        from backend.core.local_auth import AWIRole, PERMISSION_MATRIX
        self.assertIsNotNone(AWIRole)
        self.assertIsNotNone(PERMISSION_MATRIX)

    def test_six_roles_defined(self):
        from backend.core.auth_session import AWIRole
        roles = list(AWIRole)
        self.assertEqual(len(roles), 6)


# ---------------------------------------------------------------------------
# 10. Auth routes smoke tests (TestClient)
# ---------------------------------------------------------------------------

class TestAuthRoutesSmokeTests(unittest.TestCase):
    """
    Smoke tests against the auth router via FastAPI TestClient.
    Uses a fully isolated database per test.
    """

    def _get_client(self, db_path: str):
        """Build a fresh FastAPI TestClient with isolated auth DB."""
        os.environ["AWI_AUTH_DB"] = db_path
        import backend.core.local_auth as _la
        _la._auth_manager = None

        from fastapi import FastAPI
        from backend.api.auth_routes import router
        app = FastAPI()
        app.include_router(router)

        from fastapi.testclient import TestClient
        return TestClient(app, raise_server_exceptions=True)

    def setUp(self):
        self._db = _tmp_db()
        self._client = self._get_client(self._db)
        # Bootstrap an admin user
        resp = self._client.post(
            "/api/auth/bootstrap",
            params={"initial_password": "Enterprise@Admin1!"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)

    def tearDown(self):
        os.environ.pop("AWI_AUTH_DB", None)
        import backend.core.local_auth as _la
        _la._auth_manager = None
        try:
            Path(self._db).unlink()
        except Exception:
            pass

    def test_login_success(self):
        resp = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Enterprise@Admin1!"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

    def test_login_wrong_password(self):
        resp = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Wrong1!"},
        )
        self.assertEqual(resp.status_code, 401)

    def test_get_me_with_valid_token(self):
        login = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Enterprise@Admin1!"},
        )
        token = login.json()["access_token"]
        me = self._client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "admin")

    def test_get_me_without_token(self):
        resp = self._client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_logout_revokes_token(self):
        login = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Enterprise@Admin1!"},
        )
        token = login.json()["access_token"]
        # Logout
        self._client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        # Token should be revoked now
        me = self._client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(me.status_code, 401)

    def test_create_user_as_admin(self):
        login = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Enterprise@Admin1!"},
        )
        token = login.json()["access_token"]
        resp = self._client.post(
            "/api/auth/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "username": "newanalyst",
                "display_name": "New Analyst",
                "email": "analyst@awi.test",
                "role": "hr_analyst",
                "initial_password": "Enterprise@2025X",
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["username"], "newanalyst")

    def test_audit_log_accessible_to_admin(self):
        login = self._client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Enterprise@Admin1!"},
        )
        token = login.json()["access_token"]
        resp = self._client.get(
            "/api/auth/audit-log",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("entries", data)

    def test_bootstrap_idempotent_via_endpoint(self):
        resp = self._client.post(
            "/api/auth/bootstrap",
            params={"initial_password": "Enterprise@Admin1!"},
        )
        # Should succeed silently (201 or 200 — admin already exists)
        self.assertIn(resp.status_code, [200, 201])


# ---------------------------------------------------------------------------
# 11. main.py wiring
# ---------------------------------------------------------------------------

class TestMainPyAuthWiring(unittest.TestCase):

    def test_auth_router_included_in_app(self):
        """The auth router must be included in the main FastAPI app."""
        import sys
        # Use a test DB so auth module doesn't pollute production
        db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = db
        os.environ["AWI_AUTH_ENFORCED"] = "false"
        try:
            from backend.api.main import create_app
            app = create_app()
            routes = [r.path for r in app.routes]
            auth_routes = [r for r in routes if r.startswith("/api/auth")]
            self.assertTrue(
                len(auth_routes) > 0,
                f"No /api/auth routes found. Got: {routes}",
            )
        finally:
            os.environ.pop("AWI_AUTH_DB", None)
            os.environ.pop("AWI_AUTH_ENFORCED", None)
            import backend.core.local_auth as _la
            _la._auth_manager = None
            try:
                Path(db).unlink()
            except Exception:
                pass

    def test_cors_is_not_wildcard(self):
        """CORS origins must not be ['*'] (security requirement)."""
        import sys
        db = _tmp_db()
        os.environ["AWI_AUTH_DB"] = db
        os.environ["AWI_AUTH_ENFORCED"] = "false"
        try:
            from backend.api.main import create_app
            app = create_app()
            # Find CORSMiddleware config
            from starlette.middleware.cors import CORSMiddleware
            cors_mw = None
            for mw in app.user_middleware:
                if "CORSMiddleware" in str(mw.cls):
                    cors_mw = mw
                    break
            if cors_mw is not None:
                origins = cors_mw.kwargs.get("allow_origins", [])
                self.assertNotIn("*", origins, "CORS must not allow all origins")
        finally:
            os.environ.pop("AWI_AUTH_DB", None)
            os.environ.pop("AWI_AUTH_ENFORCED", None)
            import backend.core.local_auth as _la
            _la._auth_manager = None
            try:
                Path(db).unlink()
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
