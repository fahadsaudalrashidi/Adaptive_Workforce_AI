# Phase 44 — Agentic AI Business Analyst (Claude API + Registered Action Tools)

The AI Business Analyst gains a real Claude-API-driven agentic mode with 5 explicit registered tools, layered on top of — never replacing — Phase 37's local Q&A and Phase 43's sandbox, both of which remain byte-for-byte functional for users without a cloud key.

## Corrections to the task brief (verified before building anything)

Per the brief's own instruction to verify real state rather than trust its phase numbers:

- **"Phase 42" does not exist.** The real, most recently completed prior phase is **Phase 43** (`PHASE_43_SANDBOXED_AGENT_REPORT.md`) — the Windows-Job-Objects sandbox, adversarially tested against the 5 real attack vectors. This phase builds directly on that real module (`backend/core/sandbox_executor.py`, `sandbox_code_generator.py`, `sandbox_diff_summary.py`), unmodified except where a real bug was found while integrating (documented below).
- **"Phase 37"** is real and correct as named — `backend/core/ai_business_analyst_engine.py`, its `QUERY_REGISTRY` (21 registered queries), and its numeric-guard discipline. This module is **completely untouched** by Phase 44 — `answer_question()` was not edited; the new agentic path lives entirely in new modules.
- **The API key was not in the project root.** Found at `C:\Users\PvP-Pc\Desktop\apikay.txt` — on the Desktop, one directory above the project, not inside `Adaptive_Workforce_AI\`. Located via a recursive search after the assumed location came up empty.
- **The real key is valid but the account has no usable credit balance.** `anthropic.Anthropic(...).messages.create(...)` against the real key returns a genuine `400 invalid_request_error`: *"Your credit balance is too low to access the Anthropic API."* This is an authentication **success** followed by a billing failure — not an invalid key. This is documented honestly throughout rather than papered over, and it is exactly the real-world condition the graceful-degradation path had to actually handle (not a simulated one).

## 1. API key handling and graceful degradation

| Step | Result |
|---|---|
| Located | `C:\Users\PvP-Pc\Desktop\apikay.txt` (plain text, single line, one real key) |
| Migrated to | `.env` (project root) as `ANTHROPIC_API_KEY=...`, with a comment explaining the exception's scope |
| Loading mechanism | `config/settings.py` — the codebase's existing central settings module, which already read `LOG_LEVEL` via `os.environ.get(...)` but **had no `load_dotenv()` call anywhere in the entire codebase** (a real, pre-existing gap — `python-dotenv` was an installed-but-unused transitive dependency). Added one `load_dotenv()` call at the top of `config/settings.py`, before any `os.environ.get(...)` in this file or any module imported after it. `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` added following the exact same `os.environ.get(name, default)` convention as `LOG_LEVEL`. |
| `.gitignore` | Did not exist (the project isn't a git repository at all — confirmed via `git status` → "not a git repository"). Created one anyway, `.env` listed first, for when it becomes one. |
| Loose file cleanup | `C:\Users\PvP-Pc\Desktop\apikay.txt` **deleted** after its content was confirmed migrated into `.env` — per the brief's explicit instruction not to leave it sitting around. |
| Masking | `mask_api_key()` (`backend/core/cloud_llm_client.py`) — first 8 + last 4 characters. Verified live: the real key never appears in any HTTP response (`test_status_never_leaks_full_key_in_masked_form`, asserting the raw key substring is absent from the full response text) or in this report — shown here only as `sk-ant-a...rAAA`. |
| Real validation | `check_cloud_mode()` makes an **actual minimal API call** (`max_tokens=1`), not a file-existence check — cached 60s. Confirmed live against the real key: `configured=True, valid=False, detail="Key is valid (authenticated), but the Anthropic account's credit balance is too low to make requests."` — a specific, honest classification, not a generic "unavailable." |
| Graceful degradation | Structural, not a guess: `POST /api/local/ai-business-analyst/agentic` checks `check_cloud_mode()` first; if not `valid`, it calls the **exact same** `_ai_analyst_answer_question` already bound for the plain `/ai-business-analyst` route — not a reimplementation. Verified live end-to-end (see §4) against the real billing failure, not a simulated "no key" case. |
| Frontend disclosure | A persistent, impossible-to-miss amber banner ("Cloud AI mode active — questions, uploaded-data structure, and figures sent to this feature are sent to Anthropic's API...") replaces the offline banner **only** when `cloud_valid` is real-checked `true` — see `AIBusinessAnalyst.tsx`. |

## 2. Registered tools and their safety constraints

Every tool is one of exactly three kinds — Claude can never execute free code (`backend/core/agentic_tools.py`):

| Tool | Kind | Safety constraint |
|---|---|---|
| `get_business_metric` | Wraps `run_registered_query()` (Phase 37, unmodified) | `query_id` is a **closed enum** built from the real `QUERY_REGISTRY` keys — Claude cannot invent one. Verified: `test_get_business_metric_enum_matches_real_registry` asserts the schema's enum is set-equal to the live registry. An unregistered ID still raises `KeyError` inside `run_registered_query` itself, caught and returned as `available: False` — never a crash. |
| `get_variance_context` | New, but reads real dataclass fields (`period_variances`, `revenue_by_category`, `expense_by_category`, `expense_by_department`) from `FinancialIntelligenceResult` — zero new computation | Every value returned is recorded in a `VerifiedNumberPool` before being handed to Claude — this is what makes the causal-analysis guard (§3) possible. |
| `generate_pptx_report` | New, deterministic `python-pptx` | **Every number in the requested slide content must trace to a real value already fetched this turn** — checked *before* a single slide is written. Verified live with a real fabricated-number attempt: rejected with the exact untraceable number named, zero file produced. |
| `merge_excel_files` | New, deterministic `pandas.merge` | **Deliberately NOT routed through the Phase 43 sandbox** — a documented design choice: a 2-file key-column merge is a single, unambiguous operation with no room for interpretation, so a fixed function is faster, fully deterministic, and has no generated code to audit at all, unlike genuinely open-ended edit instructions. Honest errors on missing files/columns, never a fabricated merge. |
| `edit_file` | Wraps Phase 43's **unmodified** sandbox (`sandbox_code_generator` + `sandbox_executor` + `sandbox_diff_summary`) | Nothing about the 3-layer isolation changes — Claude is simply a second caller of the exact same, already-adversarially-tested execution path the local model used in Phase 43. |

**Reconciling with Phase 37's "dispatch is never LLM-driven" rule** (that module's own docstring): the original concern was *unbounded* free-form dispatch — raw LLM text output directly choosing what code runs, with no structural limit. Claude's tool-use here is schema-constrained to this exact, small, closed set of pre-vetted actions; it cannot call anything not defined above, and every metric fetch still routes through the unchanged `run_registered_query()` gate. What changed is *which mechanism* picks a tool from a fixed menu (keyword-matching vs. Claude's structured tool selection) — not whether arbitrary computation became reachable, which it did not.

## 3. Causal-analysis grounding, extended

`get_variance_context` gives the model a real multi-metric bundle (period-over-period variance %, category/department breakdowns) instead of one number, with an explicit system-prompt rule (`_SYSTEM_PROMPT` in `agentic_orchestrator.py`): the model may synthesize a narrative ("expenses rose primarily in category Y, up N%, while other categories were flat") but must never introduce an external cause not present in the tool data. This is enforced the same way as every other numeric claim — via the `VerifiedNumberPool`, checked on the final synthesized text.

**A real bug found and fixed while verifying this**: a genuinely grounded causal narrative that naturally referenced real period labels ("...from 2026-01 to 2026-02...") was initially **rejected** — the number-matching regex extracted "2026", "01", "02" as if they were separate invented figures, because only *numeric* metric values were being tracked as traceable, not the *string* period labels the tool also returned. Fixed by extending `VerifiedNumberPool` to track known-real strings too, masking every one out of the final text before the numeric regex ever runs. Verified with a dedicated regression test (`test_numeric_guard_does_not_false_positive_on_real_period_labels`) plus both directions of the causal scenario:
- A real, data-grounded explanation → **accepted**.
- The identical scenario with a fabricated `47.3%` figure and an invented "general market downturn" cause → **rejected**, fallback shown instead (`test_fabricated_external_cause_rejected`).

## 4. Live verification — all three required actions, with real outputs

**(a) Causal "why did X change" question** — real financial data (`financial_transactions_test_data.csv`), simulated Claude tool-selection (real Anthropic responses aren't obtainable right now — see the billing finding above; this uses the same injectable-`api_call` testability pattern Phase 37 already established for `phrase_with_ollama`), real tool execution, real numeric guard:
```
Real expense_by_category[0]: ('Salaries Expense', 25000.0, 67.2)
Real period_variances[0]:    ('2026-02', expense_variance_pct=18.8)

Grounded narrative (ACCEPTED, mode=claude_agent):
"Expenses increased 18.8% from 2026-01 to 2026-02. The largest expense
category is Salaries Expense at SAR 25,000.00 (67.2% of total expense)."

Fabricated narrative (REJECTED, mode=claude_agent_fallback_ungrounded):
"Expenses rose 47.3% due to a general market downturn affecting the
whole sector." -> discarded; "47.3" and "market downturn" never traceable.
```

**(b) PPTX generation** — real file, independently re-opened and inspected (not trusted from the tool's own claim):
```
generate_pptx_report("Test Report", [{"heading": "Revenue",
  "bullets": ["Total revenue: SAR 74,000.00"]}])
-> ok=True, 29185 bytes
Re-opened with python-pptx: 2 real slides.
  Slide 0: ['Test Report', 'Generated by AI Business Analyst — every figure traced to verified data']
  Slide 1: ['Revenue', 'Total revenue: SAR 74,000.00']
```
A second attempt with a fabricated number (`SAR 99999999.00`, never fetched) was rejected before any file was written — `ok=False`, the exact untraceable number named.

**(c) Excel merge** — real files, independently re-read:
```
left = {ID: [1,2,3], Name: [A,B,C]}, right = {ID: [1,2,3], Value: [10,20,30]}
merge_excel_files(..., on_column="ID", how="inner")
-> ok=True, 3 rows x 3 columns
Re-read with pandas: columns=[ID, Name, Value], Value=[10, 20, 30] — exact match.
```

**Real end-to-end HTTP round trip** (not a unit test — the actual running FastAPI route, hit via `TestClient`, against the real, currently billing-blocked key):
```
POST /api/local/ai-business-analyst/agentic  {question: "What is our total revenue?", files: [financial_transactions_test_data.csv]}
-> mode: "local_fallback"
-> cloud_status: {configured: true, valid: false, detail: "Key is valid (authenticated), but the Anthropic account's credit balance is too low to make requests."}
-> answer_text: "Our total revenue is 74,000.00 SAR."
```
Live browser screenshots (`pw_shots_phase44/`): `01_real_cloud_status_billing_blocked.png` (the real, honest status banner), `02_real_graceful_fallback_answer.png` (the real question → real correct local-fallback answer, "ANSWERED LOCALLY" label, full 6-part Phase 37 layout unchanged) — both against the genuine running app, zero console/page errors.

**Frontend rendering of the cloud-agent path** could not be captured against the real (credit-blocked) key, so it was verified with a temporary, clearly-isolated demo: a second backend process on the same port, `check_cloud_mode` and the Claude API call patched to return realistic responses, screenshotted, then **fully torn down** — the real backend was restarted immediately after and re-confirmed showing its genuine billing-blocked state (`03_DEMO_cloud_status_active.png`, `04_DEMO_cloud_agent_answer.png`, both filenames explicitly marked `DEMO`). Everything the demo displays (the "Cloud Agent (Claude)" badge, the Actions Taken list, tool names, answer text) was already independently verified for real at the Python/data level in (a)–(c) above and in the automated test suite — the demo exists only to confirm the *frontend rendering logic* for a state the real account cannot currently reach, not to fabricate a capability that doesn't work.

## 5. Test results

| Suite | Result |
|---|---|
| `test_phase44_agentic_ai.py` (tools independently, malformed calls, fallback, causal grounding) | **20/20 passed** |
| `test_phase44_agentic_workflow.py` (real HTTP route, real key) | **4/4 passed** |
| Full backend suite (`pytest tests/`) | **1284 passed**, 1 failed, 0 skipped |

The single failure (`test_phase30_1_security.py::TestMainPyAuthWiring::test_auth_router_included_in_app`) is the same pre-existing, unrelated failure documented in every phase report since Phase 40. (One previously-skipped test in the suite now passes rather than skips — an Ollama-reachability-gated test, and Ollama is running in this session; not a Phase 44 change.)

## 6. Regression count

| | Passed | Failed | Skipped |
|---|---|---|---|
| Before this phase (Phase 43 end) | 1,259 | 1 (pre-existing, unrelated) | 1 |
| After this phase | 1,284 | 1 (same pre-existing, unrelated) | 0 |

**Zero regressions.** Phase 37's local-mode path is untouched (`ai_business_analyst_engine.py` has no diff); `test_pure_local_endpoint_unaffected_by_phase_44` confirms the original `/ai-business-analyst` endpoint answers identically to before. Net +25 vs. baseline: +24 new Phase 44 tests, +1 from the environment-dependent Ollama-gated test now passing instead of skipping.

## Files added
`config/settings.py` (edited — `load_dotenv()` + `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`), `.env` (new, git-ignored), `.gitignore` (new), `backend/core/cloud_llm_client.py`, `backend/core/agentic_tools.py`, `backend/core/agentic_orchestrator.py`, `backend/api/local_analysis_routes.py` (edited — 3 new routes, `_AGENTIC_DOWNLOAD_STORE`), `executive-ui/src/pages/AIBusinessAnalyst.tsx` (edited — cloud status banner, tool list, `AgenticAnswerCard`), `tests/test_phase44_agentic_ai.py`, `tests/test_phase44_agentic_workflow.py`, `requirements.txt` (edited — `anthropic`, `python-dotenv`).
