"""
Phase 43 — end-to-end sandboxed edit-and-return workflow tests.

Exercises the real FastAPI route (/api/local/ai-business-analyst/edit-file)
via TestClient against the real backend/core/sandbox_executor.py — these
are the "real edit this Excel file end-to-end" and "real malformed request
handled honestly" tests the task brief requires, distinct from the
adversarial isolation suite in test_phase43_sandbox_isolation.py.

The live-code-generation tests are skipped (not failed) when the local
Ollama code-gen model isn't reachable, so this file doesn't become a flaky
CI failure on a machine without Ollama running — but see
PHASE_43_SANDBOXED_AGENT_REPORT.md for a real run's actual evidence,
captured against a live Ollama instance during development.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backend.core.sandbox_code_generator import code_gen_reachable
from backend.core.sandbox_windows_limits import pywin32_available


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.api.main import create_app
    app = create_app()
    return TestClient(app, raise_server_exceptions=True)


def _sample_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    pd.DataFrame({
        "Department": ["Sales", "Engineering", "HR"],
        "Headcount": [10, 25, 5],
    }).to_excel(buf, index=False)
    return buf.getvalue()


pytestmark = pytest.mark.skipif(
    not pywin32_available(), reason="pywin32 (Windows Job Objects) not installed"
)


class TestEditFileStatus:
    def test_status_endpoint_reports_real_availability(self, client):
        resp = client.get("/api/local/ai-business-analyst/edit-file/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_available"] == pywin32_available()
        assert data["code_gen_model"] == "qwen2.5-coder:7b"


@pytest.mark.skipif(not code_gen_reachable(), reason="local Ollama code-gen model not reachable")
class TestRealEditWorkflow:
    def test_real_excel_edit_end_to_end_with_verified_diff(self, client):
        """A genuine natural-language edit request, run through the real
        local code-generation model and the real sandbox — confirms a
        correct result via the independently-computed diff, not by trusting
        the LLM's own claim of what it did."""
        files = {"file": ("headcount.xlsx", _sample_xlsx_bytes(),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"instruction": "Add a new column called TotalCost that multiplies Headcount by 1000."}
        resp = client.post("/api/local/ai-business-analyst/edit-file", files=files, data=data)
        assert resp.status_code == 200
        body = resp.json()

        assert body["sandboxed_edit"] is not None
        edit = body["sandboxed_edit"]
        assert edit["fulfilled_via"] == "sandboxed_code_execution"
        assert edit["ok"] is True, f"Edit failed: {edit.get('error')}"
        assert edit["diff_summary"] is not None
        assert edit["diff_summary"]["changed"] is True
        assert edit["download_url"]

        # Independently verify by downloading and re-reading the actual file
        # — not trusting the diff_summary's own claim either.
        dl = client.get(edit["download_url"])
        assert dl.status_code == 200
        out_df = pd.read_excel(io.BytesIO(dl.content))
        assert "TotalCost" in out_df.columns
        assert out_df["TotalCost"].tolist() == [10000, 25000, 5000]

    def test_pure_question_never_touches_sandbox(self, client):
        """A pure factual question must route ONLY through the grounded
        answer_question() path — sandboxed_edit must stay null, proving the
        two paths really are architecturally separate, not just described
        as separate."""
        files = {"file": ("headcount.xlsx", _sample_xlsx_bytes(),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"instruction": "What is the total headcount?"}
        resp = client.post("/api/local/ai-business-analyst/edit-file", files=files, data=data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["sandboxed_edit"] is None
        assert body["grounded_answer"] is not None
        assert body["grounded_answer"]["fulfilled_via"] == "grounded_answer"


class TestMalformedRequestHonestFailure:
    def test_impossible_edit_request_fails_honestly(self, client):
        """An instruction referencing a column that doesn't exist in the
        real file must come back as an honest failure — never a fabricated
        success or a silently-unedited file presented as done."""
        files = {"file": ("headcount.xlsx", _sample_xlsx_bytes(),
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {"instruction": "Delete every row where the NonexistentColumnXYZ is negative."}
        resp = client.post("/api/local/ai-business-analyst/edit-file", files=files, data=data)
        assert resp.status_code == 200
        body = resp.json()
        edit = body["sandboxed_edit"]
        assert edit is not None
        if not code_gen_reachable():
            assert edit["ok"] is False
            assert "not reachable" in edit["error"]
        else:
            # Two honest outcomes are both acceptable here — what's NOT
            # acceptable is claiming a change happened when it didn't:
            #   (a) the sandbox genuinely fails (KeyError on the nonexistent
            #       column) -> ok=False, no download offered; or
            #   (b) the generated code defensively checks for the column's
            #       existence first and no-ops -> ok=True, but the diff
            #       summary must then honestly show changed=False (nothing
            #       was actually touched), never changed=True.
            if edit["ok"] is False:
                assert "download_url" not in edit
            else:
                assert edit["diff_summary"] is not None
                assert edit["diff_summary"]["changed"] is False, (
                    "Sandbox reported success editing a column that doesn't "
                    "exist in the file AND claimed a real change happened — "
                    "this would be exactly the fabricated-success failure "
                    "mode the task explicitly requires never happens."
                )
