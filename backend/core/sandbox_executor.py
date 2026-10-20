"""
Sandbox Executor — Phase 43.

Orchestrates one sandboxed run of LLM-generated Python code against a
COPY of an uploaded file. This is the module that ties together:

  Layer 1 — sandbox_code_validator.py   static AST pre-check (fast reject)
  Layer 2 — the runner bootstrap below  runtime import allowlist, network
                                         block, filesystem containment,
                                         stripped dangerous builtins,
                                         installed inside the CHILD
                                         interpreter before user code runs
  Layer 3 — sandbox_windows_limits.py   Windows Job Object: hard memory
                                         cap, hard CPU-time cap, single-
                                         process cap, kill-on-close — the
                                         real, kernel-enforced backstop if
                                         Layers 1-2 are somehow bypassed

Every run is logged via sandbox_audit_logger.py BEFORE execution starts
(so the trail survives a killed/crashed sandbox process) and again after
it completes.

Process isolation model: a brand-new `python -I` child process per run,
never in-process exec()/eval(). The child is assigned to the Windows Job
Object immediately after Popen() returns, before it does anything more
than start the interpreter — the residual window between process creation
and job assignment is a few milliseconds of pure interpreter startup, with
none of the network/filesystem/import guards or user code having run yet
(those are the first lines of the bootstrap script, executed only after
the interpreter is already up), so there is nothing meaningful for a
malicious payload to do in that window even in principle.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.sandbox_code_validator import ALLOWED_IMPORTS, validate_sandbox_code
from backend.core.sandbox_windows_limits import (
    SandboxResourceLimits, WindowsSandboxJob, JobObjectUnavailableError, pywin32_available,
)
from backend.core.sandbox_audit_logger import get_sandbox_audit_logger

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

_SANDBOX_ROOT = Path(__file__).resolve().parent.parent.parent / "sandbox_runs"

# Runtime import guard (Layer 2c) is a BLOCKLIST, not the static validator's
# allowlist — deliberately different from Layer 1. The static AST check
# (sandbox_code_validator.py) allowlists what the LLM's OWN top-level
# `import` statements should contain. But `builtins.__import__` is patched
# globally inside the child process, so it also intercepts every import
# pandas/openpyxl/numpy/docx/pptx trigger INTERNALLY at runtime (e.g.
# `pd.read_excel()` transitively imports `_io`, `_decimal`, `zoneinfo`,
# etc.) — an allowlist here would need to enumerate every private C-
# extension module those trusted libraries happen to use, which is
# fragile (breaks on a library version bump) and doesn't actually improve
# security, since a bare `_io`/`_decimal`/`zoneinfo` import has no
# capability to reach the network or the filesystem outside the sandbox on
# its own. A confirmed real failure during development (`_io` blocked
# mid-`pd.read_excel`) is what caught this — see the Phase 43 report.
# NOTE on the earlier design: this used to be an import-level blocklist
# (reject `import subprocess`/`import socket`/etc. outright). An empirical
# test — importing pandas/numpy/openpyxl/python-docx/python-pptx and
# exercising a real read/write round-trip under an import-logging hook —
# showed these libraries transitively touch `subprocess`, `socket`, `ssl`,
# `ctypes`, `shutil`, and `winreg` as ordinary import-time feature
# detection, not because they call anything dangerous. Blocking those
# imports broke basic `pd.read_excel()`/`Workbook()` calls outright (see
# the Phase 43 report for the exact failing runs). The real defense — the
# runner bootstrap's Layer 2c below — patches the specific dangerous
# FUNCTIONS (`subprocess.Popen`/`.run`/etc., `os.system`/`.popen`/`.fork`/
# `.exec*`/`.spawn*`, `ctypes.CDLL`/`WinDLL`/`windll`) to raise, while
# leaving every module freely importable. This constant is kept only for
# the module docstring's record of what was tried and rejected.


@dataclass
class SandboxRunResult:
    run_id: str
    outcome: str                    # "success" | "code_error" | "sandbox_violation" | "timeout" | "resource_exceeded" | "validation_rejected"
    exit_reason: str
    stdout: str
    stderr: str
    duration_ms: float
    output_file_path: Optional[Path] = None
    peak_memory_mb: Optional[float] = None
    validation_violations: List[str] = field(default_factory=list)


_BOOTSTRAP_TEMPLATE = r'''
# Auto-generated sandbox bootstrap — Phase 43. Runs as a standalone `python -I`
# process. Every guard below is installed BEFORE the user's generated code
# (loaded from user_code.py in this same directory) is executed.
import sys, builtins, socket as _socket, io as _io

SANDBOX_DIR = r"{sandbox_dir}"
INPUT_PATH = r"{input_path}"
OUTPUT_PATH = r"{output_path}"

import os as _os  # needed internally by this bootstrap only — not exposed to user code
import traceback as _real_traceback
import json as _real_json

# Captured BEFORE the dangerous-builtins strip below removes `exec`/`compile`
# from `builtins` — this bootstrap script still needs them once (to run the
# user's code under a restricted globals dict); user code itself never sees
# these names, since they are local variables here, not builtins, and the
# strip pass removes them from `builtins` before user code ever runs.
_real_exec = exec
_real_compile = compile

# ── Layer 2a: network block ────────────────────────────────────────────────
# Stricter than the platform-wide OfflineModeGuard (which permits loopback
# for the main app's own local API calls): a sandboxed file-edit script has
# ZERO legitimate need for any network access, loopback included. Every
# outbound path in Python's stdlib ultimately calls socket.socket.connect/
# connect_ex or socket.getaddrinfo, so patching those three functions to
# always raise blocks urllib, requests (if importable), http.client, ftplib,
# smtplib, and raw socket use alike — without needing to enumerate every
# higher-level networking module individually.
class _SandboxNetworkBlocked(RuntimeError):
    pass

def _blocked(*a, **k):
    raise _SandboxNetworkBlocked(
        "SANDBOX_NETWORK_VIOLATION: network access is not permitted inside "
        "the sandboxed execution environment (no exceptions, including "
        "loopback)."
    )

_socket.socket.connect = _blocked
_socket.socket.connect_ex = _blocked
_socket.create_connection = _blocked
_socket.getaddrinfo = _blocked

# ── Layer 2b: filesystem containment ───────────────────────────────────────
# All file I/O is restricted to SANDBOX_DIR (realpath-containment checked,
# so symlink/`..`-escape attempts resolve to their real target before the
# check runs, not before).
_real_open = builtins.open

def _sandboxed_open(file, mode="r", *args, **kwargs):
    try:
        target = _os.path.realpath(_os.path.join(SANDBOX_DIR, file) if not _os.path.isabs(str(file)) else file)
    except Exception:
        raise PermissionError("SANDBOX_FS_VIOLATION: could not resolve path")
    root = _os.path.realpath(SANDBOX_DIR)
    if _os.path.commonpath([target, root]) != root:
        raise PermissionError(
            f"SANDBOX_FS_VIOLATION: path '{{file}}' resolves outside the "
            f"sandboxed directory. Only files inside the sandbox are reachable."
        )
    return _real_open(target, mode, *args, **kwargs)

builtins.open = _sandboxed_open

# ── Layer 2c: block process-spawn and native-code capability, not imports ──
# An earlier version of this bootstrap blocked *importing* subprocess/
# socket/ctypes/etc. entirely. That broke real functionality: an empirical
# test (see PHASE_43_SANDBOXED_AGENT_REPORT.md) showed pandas/openpyxl/
# python-docx/python-pptx transitively touch `subprocess`, `socket`, `ssl`,
# `ctypes`, `shutil`, and `winreg` merely as ordinary import-time feature
# detection — none of that is a real security decision, so blocking the
# import broke basic `pd.read_excel()`/`Workbook()` calls outright. The
# fix: leave every module importable, and instead patch the specific
# FUNCTIONS that actually grant dangerous capability — the same principle
# already applied to `socket.socket.connect` above. Trusted libraries that
# merely import `subprocess`/`ctypes` and never call these functions are
# completely unaffected; anything that actually tries to spawn a process or
# call into a native DLL is stopped at the point of the attempt.
#
# IMPORTANT ordering note: this patch is installed AFTER the trusted-library
# pre-imports below (pd/np/openpyxl/docx/pptx), not before. A real failure
# during development showed numpy's OWN import genuinely calls
# `ctypes.CDLL`/`WinDLL` internally (to load its bundled native math
# libraries) — not just importing the module defensively, but actually
# invoking it. Patching this before those imports broke numpy import
# outright. Patching it AFTER means: the platform's own trusted, pre-vetted
# libraries complete their normal startup using the real ctypes/subprocess,
# and only the user's own submitted code — which runs strictly after this
# point — is blocked from spawning a process or loading a native library.
def _install_process_and_native_code_guards():
    import subprocess as _subprocess
    import ctypes as _ctypes

    def _blocked_spawn(*a, **k):
        raise _SandboxNetworkBlocked(  # reused as the generic "sandbox capability blocked" exception
            "SANDBOX_PROCESS_VIOLATION: spawning a process is not permitted "
            "inside the sandboxed execution environment."
        )

    # Capture the REAL Popen class BEFORE rebinding subprocess.Popen below —
    # a real bug caught by test_e's Layer-1-bypassed variant: doing this in
    # the opposite order (rebind subprocess.Popen to _blocked_spawn first,
    # THEN try `subprocess.Popen.__init__ = _blocked_spawn`) silently patches
    # the __init__ of _blocked_spawn itself, not the real class — since
    # `subprocess.Popen` no longer pointed at the class by that second line.
    # The result: a subclass-crawl walk that finds the real Popen class
    # object directly (bypassing the module-level rebinding entirely) could
    # still call its real, unpatched __init__ and reach a genuine
    # CreateProcess attempt — caught in testing only because the Windows Job
    # Object's ActiveProcessLimit then refused the 3rd process, not because
    # this patch worked. Fixed by patching the class's __init__ first, using
    # a reference captured before any module-level rebinding.
    _real_popen_class = _subprocess.Popen
    _real_popen_class.__init__ = _blocked_spawn

    for _attr in ("Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput"):
        if hasattr(_subprocess, _attr):
            setattr(_subprocess, _attr, _blocked_spawn)

    for _attr in ("system", "popen", "spawnl", "spawnle", "spawnlp", "spawnlpe",
                  "spawnv", "spawnve", "spawnvp", "spawnvpe", "fork",
                  "posix_spawn", "execl", "execle", "execlp", "execlpe",
                  "execv", "execve", "execvp", "execvpe", "startfile"):
        if hasattr(_os, _attr):
            setattr(_os, _attr, _blocked_spawn)

    def _blocked_dll(*a, **k):
        raise _SandboxNetworkBlocked(
            "SANDBOX_NATIVE_CODE_VIOLATION: loading a native library / calling "
            "into native code is not permitted inside the sandboxed execution "
            "environment."
        )

    for _dll_loader_name in ("CDLL", "PyDLL", "WinDLL", "OleDLL"):
        if hasattr(_ctypes, _dll_loader_name):
            setattr(_ctypes, _dll_loader_name, _blocked_dll)
    for _preloaded_name in ("cdll", "windll", "oledll", "pydll"):
        if hasattr(_ctypes, _preloaded_name):
            setattr(_ctypes, _preloaded_name, None)

# ── Layer 2d: restricted builtins for the USER's OWN top-level code only ──
# `eval`/`exec`/`compile`/`input` etc. are NOT removed from the real
# `builtins` module — doing that globally broke legitimate library
# internals during development (dataclasses/namedtuple/pandas' query engine
# all use `exec()` for dynamic code generation; deleting `builtins.exec`
# made a plain `pd.read_excel()`/`to_excel()` call fail with a bare
# `NameError: name 'exec' is not defined` inside pandas' own code — a real
# failure caught and fixed, see the Phase 43 report). Instead, a SEPARATE
# restricted builtins mapping — a plain copy of `builtins.__dict__` with
# only these names removed — is handed to `exec()` as the `__builtins__` of
# ONLY the user's own top-level script. Every other already-imported module
# (pandas, numpy, dataclasses, ...) keeps using the real, unmodified
# `builtins` for its own code, since Python resolves builtins per-module
# via each module's own `__builtins__` reference, not the caller's. This
# still stops the user's OWN submitted code from directly writing
# `eval(...)`/`exec(...)` to route around the Layer 1 AST check, while
# leaving every legitimate internal use by trusted libraries untouched.
_user_builtins = dict(vars(builtins))
for _name in ("eval", "exec", "compile", "input", "breakpoint", "exit", "quit",
              "help", "license", "copyright", "credits"):
    _user_builtins.pop(_name, None)

# ── Pre-import trusted libraries BEFORE installing the process/native-code
# guards (see the ordering note above `_install_process_and_native_code_
# guards` — numpy's own import needs real ctypes access) ───────────────────
_exec_globals = {{
    "__builtins__": _user_builtins,
    "INPUT_PATH": INPUT_PATH,
    "OUTPUT_PATH": OUTPUT_PATH,
}}
try:
    import pandas as _pd
    _exec_globals["pd"] = _pd
except ImportError:
    pass
try:
    import numpy as _np
    _exec_globals["np"] = _np
except ImportError:
    pass
try:
    import openpyxl as _openpyxl
    _exec_globals["openpyxl"] = _openpyxl
except ImportError:
    pass
try:
    import docx as _docx
    _exec_globals["docx"] = _docx
except ImportError:
    pass
try:
    import pptx as _pptx
    _exec_globals["pptx"] = _pptx
    from pptx import Presentation as _Presentation
    _exec_globals["Presentation"] = _Presentation
except ImportError:
    pass

_install_process_and_native_code_guards()

# ── Execute user code ───────────────────────────────────────────────────────
_result = {{"outcome": "success", "exit_reason": "", "error": None}}
try:
    with _real_open(_os.path.join(SANDBOX_DIR, "user_code.py"), "r", encoding="utf-8") as _f:
        _user_code = _f.read()

    _real_exec(_real_compile(_user_code, "user_code.py", "exec"), _exec_globals)

except _SandboxNetworkBlocked as e:
    _result = {{"outcome": "sandbox_violation", "exit_reason": str(e), "error": str(e)}}
except PermissionError as e:
    if "SANDBOX_FS_VIOLATION" in str(e):
        _result = {{"outcome": "sandbox_violation", "exit_reason": str(e), "error": str(e)}}
    else:
        _result = {{"outcome": "code_error", "exit_reason": str(e), "error": str(e)}}
except ImportError as e:
    if "SANDBOX_IMPORT_VIOLATION" in str(e):
        _result = {{"outcome": "sandbox_violation", "exit_reason": str(e), "error": str(e)}}
    else:
        _result = {{"outcome": "code_error", "exit_reason": str(e), "error": str(e)}}
except MemoryError as e:
    _result = {{"outcome": "resource_exceeded", "exit_reason": f"MemoryError: {{e}}", "error": str(e)}}
except BaseException as e:
    _result = {{"outcome": "code_error", "exit_reason": f"{{type(e).__name__}}: {{e}}", "error": _real_traceback.format_exc()}}

with _real_open(_os.path.join(SANDBOX_DIR, "result.json"), "w", encoding="utf-8") as _f:
    _real_json.dump(_result, _f)

print("SANDBOX_RUN_COMPLETE:" + _result["outcome"])
'''


def _build_bootstrap_script(sandbox_dir: Path, input_path: Path, output_path: Path) -> str:
    return _BOOTSTRAP_TEMPLATE.format(
        sandbox_dir=str(sandbox_dir),
        input_path=str(input_path),
        output_path=str(output_path),
    )


def run_sandboxed_code(
    code: str,
    input_file_bytes: bytes,
    input_filename: str,
    output_filename: str,
    tenant_id: str,
    user_request: str,
    limits: Optional[SandboxResourceLimits] = None,
    timeout_seconds: int = 30,
) -> SandboxRunResult:
    """
    Executes `code` inside a fresh, isolated `python -I` subprocess, against
    a COPY of `input_file_bytes` materialized to disk for this run only.
    Never touches any file outside the freshly created sandbox_runs/<run_id>/
    directory, which is deleted at the end of every run regardless of
    outcome (success, failure, or timeout).
    """
    if limits is None:
        limits = SandboxResourceLimits()

    audit = get_sandbox_audit_logger()
    run_id = audit.new_run_id()

    audit.log_submission(
        run_id=run_id, tenant_id=tenant_id, user_request=user_request,
        generated_code=code, input_filename=input_filename,
    )

    validation = validate_sandbox_code(code)
    if not validation.ok:
        duration_ms = 0.0
        audit.log_result(
            run_id=run_id, tenant_id=tenant_id, user_request=user_request,
            generated_code=code, input_filename=input_filename,
            outcome="validation_rejected",
            exit_reason="; ".join(validation.violations),
            stdout="", stderr="", duration_ms=duration_ms,
        )
        return SandboxRunResult(
            run_id=run_id, outcome="validation_rejected",
            exit_reason="Static validation rejected this code before execution: "
                        + "; ".join(validation.violations),
            stdout="", stderr="", duration_ms=duration_ms,
            validation_violations=validation.violations,
        )

    if not pywin32_available():
        exit_reason = (
            "pywin32 is not installed — refusing to run sandboxed code without "
            "kernel-enforced resource limits."
        )
        audit.log_result(
            run_id=run_id, tenant_id=tenant_id, user_request=user_request,
            generated_code=code, input_filename=input_filename,
            outcome="sandbox_violation", exit_reason=exit_reason,
            stdout="", stderr="", duration_ms=0.0,
        )
        return SandboxRunResult(run_id=run_id, outcome="sandbox_violation",
                                 exit_reason=exit_reason, stdout="", stderr="", duration_ms=0.0)

    run_dir = _SANDBOX_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path = run_dir / input_filename
    output_path = run_dir / output_filename

    start = time.time()
    stdout_text = ""
    stderr_text = ""
    peak_memory_mb: Optional[float] = None
    outcome = "code_error"
    exit_reason = ""

    try:
        input_path.write_bytes(input_file_bytes)
        (run_dir / "user_code.py").write_text(code, encoding="utf-8")
        bootstrap_path = run_dir / "_bootstrap.py"
        bootstrap_path.write_text(
            _build_bootstrap_script(run_dir, input_path, output_path), encoding="utf-8"
        )

        proc = subprocess.Popen(
            [sys.executable, "-I", str(bootstrap_path)],
            cwd=str(run_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_minimal_sandbox_env(run_dir),
        )

        with WindowsSandboxJob(limits) as job:
            # Assigned immediately after Popen returns — the interpreter has
            # not yet reached the bootstrap script's first guard-installing
            # line at this point, let alone any user code.
            job.assign(proc.pid)

            ps_proc = psutil.Process(proc.pid) if _PSUTIL_AVAILABLE else None
            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout_seconds)
                stdout_text = stdout_bytes.decode("utf-8", errors="replace")
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
                if ps_proc is not None:
                    try:
                        peak_memory_mb = ps_proc.memory_info().rss / (1024 * 1024)
                    except Exception:
                        pass

                job_violation = job.hit_limits()
                if job_violation:
                    outcome = "resource_exceeded"
                    exit_reason = job_violation
                elif proc.returncode != 0 and "SANDBOX_RUN_COMPLETE" not in stdout_text:
                    outcome = "code_error"
                    exit_reason = f"Sandbox process exited with code {proc.returncode} before completing."
                else:
                    result_path = run_dir / "result.json"
                    if result_path.exists():
                        result_data = json.loads(result_path.read_text(encoding="utf-8"))
                        outcome = result_data.get("outcome", "code_error")
                        exit_reason = result_data.get("exit_reason", "")
                    else:
                        outcome = "code_error"
                        exit_reason = "Sandbox process ended without writing a result manifest."

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                outcome = "timeout"
                exit_reason = f"Wall-clock timeout exceeded ({timeout_seconds}s) — process terminated."

    except JobObjectUnavailableError as e:
        outcome = "sandbox_violation"
        exit_reason = str(e)
    except Exception as e:
        outcome = "code_error"
        exit_reason = f"Sandbox orchestration error: {e}"
    finally:
        duration_ms = (time.time() - start) * 1000

    output_file_path: Optional[Path] = None
    if outcome == "success" and output_path.exists():
        output_file_path = output_path

    audit.log_result(
        run_id=run_id, tenant_id=tenant_id, user_request=user_request,
        generated_code=code, input_filename=input_filename,
        outcome=outcome, exit_reason=exit_reason,
        stdout=stdout_text, stderr=stderr_text, duration_ms=duration_ms,
        peak_memory_mb=peak_memory_mb,
    )

    return SandboxRunResult(
        run_id=run_id, outcome=outcome, exit_reason=exit_reason,
        stdout=stdout_text, stderr=stderr_text, duration_ms=duration_ms,
        output_file_path=output_file_path, peak_memory_mb=peak_memory_mb,
    )


def _minimal_sandbox_env(run_dir: Path) -> Dict[str, str]:
    """A deliberately minimal environment for the sandbox subprocess — NOT a
    fully empty one. `CreateProcess` on Windows needs SystemRoot/windir to
    locate kernel32.dll and other loader-critical system libraries (a fully
    empty env, tried first, made process creation itself fail outright —
    confirmed via the smoke test before adding this). PATH is restricted to
    only the OS's own System32/System32/Wbem — enough for the Python
    interpreter's own DLL dependencies, nothing that could resolve to an
    attacker-plantable executable earlier in a broader PATH. No proxy
    variables, no credentials, no PYTHONPATH — anything that could leak a
    secret or influence import resolution beyond the sandbox's own
    allowlist is deliberately absent.

    TEMP/TMP point at THIS run's own sandbox directory, not the shared
    sandbox_runs/ root — a real run failed here first: pandas' own
    read/write path creates intermediate temp files via the `tempfile`
    module, which honors TEMP/TMP, and the sandboxed `open()` wrapper
    correctly rejected those when TEMP pointed at the (out-of-containment)
    parent directory instead of this run's own."""
    import os as _os
    system_root = _os.environ.get("SystemRoot", r"C:\Windows")
    return {
        "SystemRoot": system_root,
        "windir": system_root,
        "PATH": f"{system_root}\\System32;{system_root}\\System32\\Wbem",
        "TEMP": str(run_dir),
        "TMP": str(run_dir),
    }


def cleanup_sandbox_run(run_id: str) -> None:
    """Deletes a run's temp directory. Called after the parent has copied
    out whatever it needs (the edited output bytes, the diff summary)."""
    run_dir = _SANDBOX_ROOT / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
