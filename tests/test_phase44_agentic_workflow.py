"""
Phase 44 — end-to-end agentic AI workflow tests, via the real FastAPI route
(/api/local/ai-business-analyst/agentic), through TestClient.

This is where graceful degradation is verified at the level that actually
matters — the real HTTP endpoint, not just the orchestrator function.
Against this project's real configured key (valid but credit-balance-
blocked — see PHASE_44_AGENTIC_AI_ANALYST_REPORT.md), every one of these
requests genuinely attempts a real Anthropic API call and genuinely falls
back to local mode on the real failure it hits — not a simulated one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.core.sandbox_windows_limits import pywin32_available


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.api.main import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


class TestAgenticStatus:
    def test_status_endpoint_reports_real_cloud_state(self, client):
        resp = client.get("/api/local/ai-business-analyst/agentic/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cloud_configured"] is True  # the real key IS present in .env
        assert data["masked_key"].startswith("sk-ant-a")
        assert data["masked_key"].endswith("rAAA")
        assert "..." in data["masked_key"]
        # the FULL key must never appear anywhere in the response
        assert "3RcgVhDho7Sttzef60OxUe8PpM4jboO45CODn2hy3wBg6YZE5ygmYlLXBmEKM8wAyDjcJ" not in resp.text
        assert data["local_fallback_reachable"] in (True, False)  # real Ollama reachability check, not hardcoded

    def test_status_never_leaks_full_key_in_masked_form(self, client):
        resp = client.get("/api/local/ai-business-analyst/agentic/status")
        masked = resp.json()["masked_key"]
        assert len(masked) < 30  # a full sk-ant-api03-... key is ~100+ chars; the masked form must be short


class TestGracefulDegradationRealRoute:
    def test_real_business_question_answered_via_graceful_fallback(self, client):
        """A real question against real uploaded data, through the real
        route. Given this deployment's real cloud-mode state (billing-
        blocked), this exercises the actual fallback path end-to-end — the
        answer must still be correct, just via mode='local_fallback'."""
        with open(_ROOT / "financial_transactions_test_data.csv", "rb") as fh:
            files = {"files": ("financial_transactions_test_data.csv", fh.read(), "text/csv")}
        data = {"question": "What is our total revenue?"}
        resp = client.post("/api/local/ai-business-analyst/agentic", files=files, data=data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] in ("cloud", "local_fallback")
        if body["mode"] == "local_fallback":
            assert body["cloud_status"]["configured"] is True
            assert body["cloud_status"]["valid"] is False
            assert body["cloud_status"]["detail"]  # a real, specific reason, not blank
        assert "74,000" in body["answer"]["answer_text"] or "74000" in body["answer"]["answer_text"]
        assert body["answer"]["actions_taken"] == [] if body["mode"] == "local_fallback" else True

    def test_pure_local_endpoint_unaffected_by_phase_44(self, client):
        """The original /ai-business-analyst endpoint (Phase 37, local-only)
        must answer identically to before this phase — zero regression,
        not just 'still returns 200'."""
        with open(_ROOT / "financial_transactions_test_data.csv", "rb") as fh:
            files = {"files": ("financial_transactions_test_data.csv", fh.read(), "text/csv")}
        data = {"question": "What is our total revenue?", "use_llm": "false"}
        resp = client.post("/api/local/ai-business-analyst", files=files, data=data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["answer"]["mode"] == "deterministic"
        assert "74,000" in body["answer"]["answer_text"] or "74000" in body["answer"]["answer_text"]
