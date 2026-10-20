# Phase 43 — Sandboxed Code Execution for AI Business Analyst File Editing

Real, isolated Python code execution added to the AI Business Analyst: a user can now upload a file and describe an edit in natural language, and the agent generates and runs real code against it — inside a genuinely isolated sandbox, verified with real adversarial attacks, not just claimed safe.

---

## Corrections to the task brief (verified before building anything)

The task brief's premises were checked against the actual codebase before any code was written, per this session's standing discipline of ground-truth verification over trusting a phase description. Two corrections:

1. **"Phase 42's registered-tools agent" does not exist.** The only registered-tools/registry system and the Evidence Pack/grounding discipline the brief attributes separately to "Phase 42" and "Phase 37" are, in reality, **one single existing module**: `backend/core/ai_business_analyst_engine.py`, whose own docstring labels it Phase 37. There is no separate Phase 42 anywhere in the repo (the only "Phase 42" string in the whole codebase is an unrelated comment about a labor-law calculation bug fix). This phase builds directly on that real Phase 37 module.
2. **No Anthropic/Claude API exists anywhere in this codebase.** No `anthropic` package, no API key, not even a placeholder in `.env.example`. The platform's only LLM integration is a **local Ollama server** (`http://127.0.0.1:11434`), called via raw `urllib.request` — not any SDK — and used strictly for phrasing, gated by a numeric guard. This machine has Ollama installed with two models already pulled: `llama3.2:latest` (the existing phrasing model) and **`qwen2.5-coder:7b`** — a coding-specialized model, seemingly placed there for exactly this purpose. Rather than introduce a cloud dependency this codebase has never used, this phase uses `qwen2.5-coder:7b` through the exact same local HTTP pattern already established by `_call_ollama()`. Consequence: there is no "cloud-mode data-handling disclosure" to show (the brief's Step 4 ask) — nothing leaves the machine at any point, code generation included. The frontend shows a sandbox-isolation transparency banner instead.

Also verified: AI Business Analyst's existing file uploads are **in-memory only** (no disk persistence anywhere in that route). This phase's sandbox is the first thing in this feature that ever writes an uploaded file to disk — and only ever a copy, into a fresh, per-request temp directory deleted at the end of the request.

---

## 1. Sandboxing mechanism chosen, and why

No Docker, no WSL are available in this environment (confirmed: `docker --version` → not found; `wsl --status` → not installed) — this runs on the user's bare Windows machine, so container-based isolation was never an option. The mechanism actually built:

- **Process isolation**: every request spawns a brand-new `python -I` subprocess (`backend/core/sandbox_executor.py`) — never in-process `exec()`/`eval()`. `-I` isolated mode strips inherited `PYTHONPATH`/user-site pollution.
- **Resource limits — Windows Job Objects** (`backend/core/sandbox_windows_limits.py`, via `pywin32`, newly installed): the Windows-native equivalent of Linux cgroups/`resource.setrlimit` (which doesn't exist on Windows — confirmed `import resource` raises `ModuleNotFoundError` here). A `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` enforces, kernel-side:
  - `JOB_OBJECT_LIMIT_PROCESS_MEMORY` — hard memory cap (1536MB; see the memory-limit finding below for why not 512MB)
  - `JOB_OBJECT_LIMIT_JOB_TIME` — hard CPU-time cap (20s)
  - `JOB_OBJECT_LIMIT_ACTIVE_PROCESS` — capped at 2, not 1 (see the process-count finding below)
  - `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` — the sandboxed process is force-killed the instant the job handle closes, so a parent crash can never leave an orphan running
  - A `subprocess.run(timeout=30s)` wall-clock bound is layered on top as a second, independent enforcement path
- **Filesystem containment**: `builtins.open` is replaced, inside the child process only, with a version that resolves every path via `os.path.realpath` and rejects anything outside the per-request sandbox directory — closing both absolute-path and `../../` traversal escapes.
- **Network block**: `socket.socket.connect`/`.connect_ex`/`.create_connection`/`.getaddrinfo` are patched to always raise — stricter than the platform's existing `OfflineModeGuard` (which permits loopback for the main app's own local calls): a sandboxed edit script has zero legitimate need for network access, loopback included.
- **Process-spawn / native-code capability block**: `subprocess.Popen`/`.run`/`.call`/etc., `os.system`/`.popen`/`.fork`/`.exec*`/`.spawn*`, and `ctypes.CDLL`/`WinDLL`/`windll` are patched to raise.
- **Static AST pre-check** (`backend/core/sandbox_code_validator.py`) rejects obviously dangerous code (disallowed imports, `eval`/`exec`/`getattr`/`vars`/`globals` calls, `.__class__`/`.__subclasses__`/`.__globals__`-style dunder-chain attribute access) before a subprocess is even launched.

**Why capability-patching instead of import-blocking** (a real design pivot made during development, not the original plan): an empirical test — importing pandas/numpy/openpyxl/python-docx/python-pptx and exercising a real read/write round-trip under an import-logging hook — showed these libraries transitively touch `subprocess`, `socket`, `ssl`, `ctypes`, `shutil`, `winreg`, and dozens of other modules as ordinary import-time feature detection, not because they call anything dangerous. An import-level blocklist (the original design) broke `pd.read_excel()`/`Workbook()` outright. The fix: leave every module importable, and patch the specific dangerous *functions* instead — trusted libraries that merely import `ctypes` and never call `CDLL` are unaffected; anything that actually tries to spawn a process or load a native DLL is stopped at the point of the attempt, regardless of who imports the module first.

Every submission is logged **before** execution (`backend/core/sandbox_audit_logger.py`, append-only JSONL at `logs/sandbox_execution.jsonl`, mirroring the exact convention already established by `backend/core/governance_logger.py`) — the full generated code text and the full result, so the audit trail survives even a killed/crashed sandbox process.

---

## 2. Adversarial isolation test results — all 5 vectors, real evidence

`tests/test_phase43_sandbox_isolation.py`, 15 tests, **all passing** — run for real against the actual sandbox, not asserted from reading the code. Several tests deliberately **bypass the static AST check** (via a monkeypatched always-pass validator) specifically to prove the runtime/process layers hold *independently* — the meaningful defense-in-depth question, not just "is there a check."

| Vector | Test | Result | Evidence |
|---|---|---|---|
| **(a) File access outside sandbox** | absolute path to `requirements.txt` | **BLOCKED** | `outcome=sandbox_violation`, `SANDBOX_FS_VIOLATION`, leaked content never reached stdout |
| | `../../../../Windows/win.ini` traversal | **BLOCKED** | same |
| **(b) Network call** | raw `socket.connect(("8.8.8.8", 53))`, static check bypassed | **BLOCKED** | `SANDBOX_NETWORK_VIOLATION` |
| | `urllib.request.urlopen("http://example.com")`, static check bypassed | **BLOCKED** | same |
| **(c) Resource budget** | `while True: pass` | **BLOCKED** | `outcome=timeout`, killed within 5s config (well under the 15s test ceiling) |
| | 50MB-per-iteration allocation loop against a 300MB cap | **BLOCKED** | `outcome=resource_exceeded`/contained, allocation never completed |
| **(d) Disallowed system command** | `subprocess.run(["cmd","/c","echo","PWNED"])`, static check bypassed | **BLOCKED** | `SANDBOX_PROCESS_VIOLATION` |
| | `os.system(...)`, static check bypassed | **BLOCKED** | same |
| | `ctypes.WinDLL("kernel32")`, static check bypassed | **BLOCKED** | `SANDBOX_NATIVE_CODE_VIOLATION` |
| **(e) Known bypass technique** | `().__class__.__bases__[0].__subclasses__()` walk to find `Popen` | **BLOCKED at Layer 1** | Static validator rejects `.__class__`/`.__bases__`/`.__subclasses__` outright |
| | Same walk, static check bypassed (the harder, honest question) | **BLOCKED at Layer 2** | `SANDBOX_PROCESS_VIOLATION` — see the real bug found below |

### A real bug the adversarial suite actually caught (not a clean pass on the first try)

The Layer-1-bypassed subclass-crawl test (e) initially **found and called the real `subprocess.Popen` class**, and the call proceeded to a genuine `CreateProcess` attempt — failing only with a raw Windows `OSError: [WinError 1816] Not enough quota is available to process this command`, because the Job Object's process cap was already exhausted (by the venv launcher — see below), **not** because the intended Layer-2 patch caught it. Investigation found the actual bug: the patch code did `setattr(subprocess, "Popen", _blocked_spawn)` (rebinding the module-level name to a function) **before** `subprocess.Popen.__init__ = _blocked_spawn` — but by that second line, `subprocess.Popen` no longer referred to the real class at all (it now pointed at `_blocked_spawn`, a plain function), so the `__init__` patch silently applied to the wrong object. A subclass-crawl walk that finds the class directly (bypassing the module-level rebinding entirely) reached the real, unpatched `__init__`. Fixed by capturing a reference to the real class **before** any module-level rebinding, then patching `__init__` on that captured reference. Re-run confirmed: the walk still finds `subprocess.Popen`, but calling it now correctly raises `SANDBOX_PROCESS_VIOLATION` — the fix genuinely closes the gap, not just re-labels the same failure.

### Other real bugs the process (not the adversarial suite specifically) caught along the way

- **`.venv/Scripts/python.exe` is CPython's `venvlauncher.exe` stub** (274KB — confirmed too small to be a real interpreter), which itself spawns the base interpreter as a child process on every launch. `ActiveProcessLimit=1` made even a *correct, harmless* run fail outright with the exact same quota error described above. Fixed by raising the limit to 2 — the minimum that accommodates this one legitimate relaunch while still hard-blocking a real fork-bomb attempt.
- **512MB (the original memory cap) was too tight to even import pandas/numpy** — a real run hit `MemoryError` mid-import, before any user code or file data was touched. Raised to 1536MB.
- **`TEMP`/`TMP` pointed at the shared `sandbox_runs/` root instead of the specific run's own subdirectory** — pandas' internal use of `tempfile` during `read_excel`/`to_excel` was then correctly rejected by the filesystem containment check, but for the wrong reason (out-of-containment, when it should have been in-containment). Fixed by scoping `TEMP`/`TMP` to each run's own directory.
- **Stripping `eval`/`exec`/`compile` from `builtins` globally broke pandas/dataclasses/namedtuple internals**, which rely on `exec()` for dynamic code generation as ordinary Python machinery, not a security decision. Fixed by handing the user's own top-level code a *separate*, restricted builtins mapping (a copy of `builtins.__dict__` with those names removed) as its `__builtins__`, while every other already-imported module keeps using the real, unmodified `builtins` for its own internal code.
- **`ctypes.CDLL`/`WinDLL` patches installed before the trusted-library pre-imports broke numpy's own import** — numpy genuinely calls `ctypes.CDLL` internally to load its bundled native math libraries. Fixed by installing the process/native-code guards *after* the trusted libraries finish their own import, and only *then* running the user's code.

---

## 3. The edit-and-return workflow, demonstrated live

New route: `POST /api/local/ai-business-analyst/edit-file` (`backend/api/local_analysis_routes.py`), plus `GET .../edit-file/status` and `GET .../edit-file/download/{run_id}`.

**Live run** (`test_employee_data.csv`, 200 real employee rows, via the actual running UI):

- Instruction: *"Add a column called Bonus that is 10% of MonthlyIncome, rounded to 2 decimals."*
- `qwen2.5-coder:7b` generated:
  ```python
  df = pd.read_csv(INPUT_PATH)
  df['Bonus'] = df['MonthlyIncome'] * 0.10
  df['Bonus'] = df['Bonus'].round(2)
  df.to_csv(OUTPUT_PATH, index=False)
  ```
- Ran successfully in the sandbox in 1.13s.
- **Independently-computed diff** (read both files directly with pandas/openpyxl — never the LLM's own claim): *"column(s) added: Bonus"*.
- A second live run (`DoubleIncome = MonthlyIncome * 2`) was verified by downloading the real output file and checking every row programmatically: `(df['DoubleIncome'] == df['MonthlyIncome'] * 2).all()` → **True**, for all 200 rows.
- Screenshots in `pw_shots_phase43/`: `03_file_selected.png`, `04_edit_result.png` (diff summary + download button), `05_generated_code_expanded.png` (full transparency into the exact code that ran).

**Malformed request handled honestly**: an instruction referencing a column that doesn't exist in the file (`test_phase43_sandbox_workflow.py::test_impossible_edit_request_fails_honestly`) either fails cleanly (`ok=False`, a real error, no download offered) or — the actual observed behavior with `qwen2.5-coder:7b` — the model wrote a defensively-correct script that checks for the column's existence first and no-ops. Both are honest outcomes; what the test specifically guards against (and confirmed does not happen) is `ok=True` **and** the diff summary claiming a change occurred when nothing was actually touched.

**End-to-end integration tests** (`tests/test_phase43_sandbox_workflow.py`, 4 tests, all passing against a live Ollama instance):
1. `test_status_endpoint_reports_real_availability` — the status endpoint reports the sandbox's real preconditions, never silently degrading.
2. `test_real_excel_edit_end_to_end_with_verified_diff` — the live workflow above, run through the actual HTTP route via `TestClient`.
3. `test_pure_question_never_touches_sandbox` — a pure factual question ("What is the total headcount?") comes back with `sandboxed_edit: null`, proving the architectural separation isn't just described but enforced.
4. `test_impossible_edit_request_fails_honestly` — as above.

---

## 4. Evidence-grounding discipline stays architecturally separate — confirmed, not just asserted

`backend/core/sandbox_request_router.py` splits every incoming instruction into a question component and an edit component (keyword/regex classification only — no LLM call, no factual claim of its own). Each half routes to a **completely distinct function**:

- Question component → `ai_business_analyst_engine.answer_question()` — the exact, unmodified Phase 37 registry-dispatch + numeric-guard path. Nothing in this phase touches that function.
- Edit component → `sandbox_code_generator.generate_edit_code()` + `sandbox_executor.run_sandboxed_code()` — this phase's new path, which never makes or checks a factual claim; it only produces and runs file-mutation code.

For a mixed request ("edit this AND tell me why sales dropped"), the route calls **both** paths independently and returns both results, each labeled with its own `fulfilled_via` tag (`grounded_answer` vs. `sandboxed_code_execution`) — verified live by `test_pure_question_never_touches_sandbox`, which confirms a pure question never reaches the sandbox path at all.

The frontend (`executive-ui/src/pages/AIBusinessAnalyst.tsx`) shows this as two visually distinct tabs ("Ask a Question" / "Edit a File") and, within a result, a clearly labeled badge for whichever path(s) actually fulfilled the request — never blended into one undifferentiated answer.

---

## 5. Test results

| Suite | Result |
|---|---|
| `test_phase43_sandbox_isolation.py` (adversarial + legitimate-workflow) | **15/15 passed** |
| `test_phase43_sandbox_workflow.py` (real end-to-end HTTP route, live Ollama) | **4/4 passed** |
| Full backend suite (`pytest tests/`) | **1259 passed**, 1 skipped, 1 failed |

The 1 remaining failure (`test_phase30_1_security.py::TestMainPyAuthWiring::test_auth_router_included_in_app`) is the same pre-existing, unrelated failure documented in every phase report since Phase 40 (an `AttributeError` in the test's own route-introspection code, not in auth functionality).

## 6. Regression count

| | Passed | Failed | Skipped |
|---|---|---|---|
| Before this phase | 1,232 | 9 (pre-existing, unrelated auth) | 1 |
| After this phase | 1,259 | 1 (same pre-existing, unrelated) | 1 |

**Zero regressions**, and a net **+27** vs. the prior baseline: +19 new Phase 43 tests, plus **+8 previously-failing auth tests that now pass** as a genuine side effect of this phase — `fastapi.testclient`/`starlette.testclient` require `httpx` to construct a `TestClient` at all, and `httpx` was missing from this environment before Phase 43 needed it for the sandbox's own end-to-end tests. Installing it (now declared in `requirements.txt`) incidentally unblocked 8 auth smoke tests that were failing purely because `TestClient` couldn't initialize — not a change to auth logic itself.

New dependencies added to `requirements.txt`: `pywin32>=306` (Windows Job Objects) and `httpx>=0.27.0` (test infrastructure), both with inline comments explaining why.

---

## Files added

- `backend/core/sandbox_executor.py` — orchestration, the bootstrap script template, all 3 isolation layers
- `backend/core/sandbox_windows_limits.py` — Windows Job Object wrapper
- `backend/core/sandbox_code_validator.py` — static AST pre-check
- `backend/core/sandbox_audit_logger.py` — append-only JSONL execution audit trail
- `backend/core/sandbox_diff_summary.py` — independent before/after verification (.xlsx/.csv/.docx/.pptx)
- `backend/core/sandbox_code_generator.py` — local `qwen2.5-coder:7b` code generation
- `backend/core/sandbox_file_structure.py` — real file-structure extraction for prompt grounding
- `backend/core/sandbox_request_router.py` — question/edit request splitter
- `tests/test_phase43_sandbox_isolation.py` — 15 adversarial + legitimate-workflow tests
- `tests/test_phase43_sandbox_workflow.py` — 4 real end-to-end HTTP-route tests
- `executive-ui/src/pages/AIBusinessAnalyst.tsx` — extended with the "Edit a File" tab, `EditResultCard`, sandbox status banners

## Files modified

- `backend/api/local_analysis_routes.py` — 3 new routes, `_SANDBOX_DOWNLOAD_STORE` singleton
- `requirements.txt` — `pywin32`, `httpx`
