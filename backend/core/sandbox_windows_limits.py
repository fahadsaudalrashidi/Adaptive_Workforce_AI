"""
Windows Job Object resource limiter — Phase 43.

Why Job Objects: this platform runs on the user's Windows machine (see
Phase 40/41's live-verification pattern — python backend/api/main.py on
Windows, no Docker/WSL present in this environment — confirmed by checking
before writing this module). Job Objects are the Windows-native equivalent
of Linux cgroups/`resource.setrlimit`: the OS kernel itself enforces the
limit on the process, not a Python-level check the sandboxed code could
race or outlast. A `subprocess.run(timeout=...)` alone only bounds wall
clock from the PARENT's side (a `while True: pass` loop is still killed
correctly by that alone) but does nothing for memory — a single large
allocation can OOM the host before the parent's timeout ever fires. A Job
Object's JOB_OBJECT_LIMIT_PROCESS_MEMORY is enforced by the Windows memory
manager itself: the allocation fails inside the child process the instant
the cap is hit, before the host is affected.

This is deliberately NOT implemented as an in-process resource.setrlimit
call (that module doesn't exist on Windows — confirmed: `import resource`
raises ModuleNotFoundError on this machine) and NOT as a psutil polling
loop from the parent (polling has a window between checks where a memory
bomb can already have done damage; a Job Object's cap is instantaneous and
kernel-enforced). psutil IS still used as a secondary, informational
peak-memory reading for the audit log — never as the actual enforcement
mechanism.

Limits applied, all via one JOBOBJECT_EXTENDED_LIMIT_INFORMATION:
  - JOB_OBJECT_LIMIT_PROCESS_MEMORY   hard cap on the child's committed memory
  - JOB_OBJECT_LIMIT_JOB_TIME         hard cap on total CPU time across the job
  - JOB_OBJECT_LIMIT_ACTIVE_PROCESS   caps the job to 2 processes — NOT 1.
                                       This venv's `Scripts/python.exe` is
                                       CPython's `venvlauncher.exe` stub
                                       (~270KB, confirmed by file size — far
                                       too small to be a real interpreter):
                                       it CreateProcess's the actual base
                                       interpreter as its own child on every
                                       launch, which is process #2 in the
                                       job. A limit of 1 made even a correct,
                                       harmless run fail outright (confirmed
                                       via a real failed smoke-test run
                                       before this was caught and fixed — see
                                       the Phase 43 report). A limit of 2
                                       accommodates that one legitimate
                                       relaunch while still hard-blocking any
                                       real fork-bomb / helper-process spawn
                                       attempt by the sandboxed code itself.
  - JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE  child is force-killed the moment the
                                       job handle is closed, so a parent crash
                                       or early return can never leave an
                                       orphaned sandboxed process running
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import win32api
    import win32con
    import win32job
    import win32process
    import pywintypes
    _WIN32_AVAILABLE = True
except ImportError:
    _WIN32_AVAILABLE = False


class JobObjectUnavailableError(RuntimeError):
    """Raised when Job Object limiting cannot be applied — the sandbox
    executor treats this as fatal, never silently runs without limits."""


@dataclass
class SandboxResourceLimits:
    # 512MB was the original default and proved too tight in practice: a
    # real run hit a genuine MemoryError just IMPORTING pandas/numpy (large
    # libraries with real import-time overhead — compiling/loading bytecode
    # for many submodules), before any user code or file data was even
    # touched. 1536MB leaves real headroom for import overhead plus a
    # reasonably sized spreadsheet/document in memory, while still bounding
    # a genuine memory-bomb far below exhausting the host.
    max_memory_mb: int = 1536
    max_cpu_seconds: int = 20


class WindowsSandboxJob:
    """
    Wraps one Windows Job Object bound to exactly one sandboxed child
    process. Use as a context manager so the job (and therefore the child,
    per JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE) is always torn down.
    """

    def __init__(self, limits: SandboxResourceLimits):
        if not _WIN32_AVAILABLE:
            raise JobObjectUnavailableError(
                "pywin32 is not installed — cannot enforce hard memory/CPU "
                "limits on this Windows host. Refusing to run sandboxed code "
                "without kernel-enforced resource limits (never fall back to "
                "running unconfined)."
            )
        self._limits = limits
        self._handle = None

    def __enter__(self) -> "WindowsSandboxJob":
        self._handle = win32job.CreateJobObject(None, "")

        info = win32job.QueryInformationJobObject(
            self._handle, win32job.JobObjectExtendedLimitInformation
        )
        info["BasicLimitInformation"]["LimitFlags"] = (
            win32job.JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | win32job.JOB_OBJECT_LIMIT_JOB_TIME
            | win32job.JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        info["ProcessMemoryLimit"] = self._limits.max_memory_mb * 1024 * 1024
        # PerJobUserTimeLimit is in 100-nanosecond units
        info["BasicLimitInformation"]["PerJobUserTimeLimit"] = int(
            self._limits.max_cpu_seconds * 10_000_000
        )
        info["BasicLimitInformation"]["ActiveProcessLimit"] = 2

        win32job.SetInformationJobObject(
            self._handle, win32job.JobObjectExtendedLimitInformation, info
        )
        return self

    def assign(self, pid: int) -> None:
        """Assign a live child process (by PID) to this job. Must be called
        immediately after the child is spawned, before it does any work —
        the earlier this happens, the smaller the unconfined-execution
        window (spawned suspended is stronger still; see sandbox_executor)."""
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
        try:
            win32job.AssignProcessToJobObject(self._handle, handle)
        finally:
            win32api.CloseHandle(handle)

    def hit_limits(self) -> Optional[str]:
        """Check whether the job's memory or time limit has been exceeded.
        Returns a human-readable reason string, or None if within limits."""
        try:
            acct = win32job.QueryInformationJobObject(
                self._handle, win32job.JobObjectBasicAccountingInformation
            )
        except pywintypes.error:
            return None
        # TotalUserTime is 100ns units
        cpu_seconds = acct["TotalUserTime"] / 10_000_000
        if cpu_seconds >= self._limits.max_cpu_seconds:
            return f"CPU time limit exceeded ({cpu_seconds:.1f}s >= {self._limits.max_cpu_seconds}s)"
        return None

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._handle is not None:
            try:
                win32job.TerminateJobObject(self._handle, 1)
            except pywintypes.error:
                pass
            try:
                win32api.CloseHandle(self._handle)
            except pywintypes.error:
                pass
            self._handle = None


def pywin32_available() -> bool:
    return _WIN32_AVAILABLE
