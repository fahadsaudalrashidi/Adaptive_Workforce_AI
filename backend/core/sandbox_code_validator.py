"""
Sandbox Code Validator — Phase 43 (formerly mis-described as "Phase 42" in
the originating task brief; see PHASE_43_SANDBOXED_AGENT_REPORT.md for the
correction — the real prior system is Phase 37's ai_business_analyst_engine.py).

STATIC (AST-level) pre-execution check — Layer 1 of the sandbox's
defense-in-depth. This is NOT the security boundary; it is a fast, cheap
reject of naive or unobfuscated attempts, run BEFORE spending a subprocess
launch on code that is obviously trying to import a disallowed module or
walk the classic `().__class__.__bases__[0].__subclasses__()`-style
sandbox-escape chain. A sufficiently obfuscated payload (e.g. computing
attribute names via string concatenation/`chr()`, or via `getattr` with a
dynamically-built string) can defeat this layer — that is expected and is
exactly why Layer 3 (process isolation: no network, filesystem confined to
the sandbox directory, Windows Job Object memory/CPU/time caps — see
sandbox_windows_limits.py and sandbox_executor.py) is the REAL backstop,
not this module. See adversarial test (e) in the Phase 43 report for a
demonstration of this layer's actual, honest coverage.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import List

# Modules the sandboxed code is permitted to import. Deliberately narrow —
# only what real file-editing/analysis tasks need. `os` and `sys` are
# excluded entirely (not just os.system): the runner bootstrap hands the
# user's code fixed INPUT_PATH/OUTPUT_PATH string constants, so there is no
# legitimate need for path-manipulation via `os` in a typical request, and
# excluding the whole module is a simpler, smaller attack surface than
# trying to allow "safe" os.path functions while blocking os.system.
ALLOWED_IMPORTS = frozenset({
    "pandas", "numpy", "openpyxl", "docx", "pptx", "datetime", "math", "re",
    "json", "decimal", "io", "string", "collections", "itertools", "statistics",
    "openpyxl.styles", "openpyxl.utils", "openpyxl.chart", "docx.shared",
    "docx.enum", "docx.enum.text", "pptx.util", "pptx.enum",
})

# Dunder names that appear in every publicly-known pure-Python sandbox
# escape technique (subclass-crawling to reach os/subprocess, frame/closure
# introspection to reach __builtins__, etc.). Any AST Attribute or Name
# referencing one of these is rejected outright.
_DANGEROUS_DUNDERS = frozenset({
    "__class__", "__bases__", "__base__", "__subclasses__", "__mro__",
    "__globals__", "__builtins__", "__import__", "__loader__", "__spec__",
    "__code__", "__closure__", "__func__", "__self__", "__getattribute__",
    "__reduce__", "__reduce_ex__", "__init_subclass__", "__subclasshook__",
    "__dict__", "__module__", "__weakref__", "__init__",
})

_DANGEROUS_CALL_NAMES = frozenset({
    "eval", "exec", "compile", "getattr", "setattr", "delattr", "vars",
    "globals", "locals", "__import__", "input", "breakpoint", "exit", "quit",
})


@dataclass
class ValidationResult:
    ok: bool
    violations: List[str] = field(default_factory=list)


def validate_sandbox_code(code: str) -> ValidationResult:
    """Static pre-execution check. Returns ok=False with a list of every
    violation found (not just the first) if the code should be rejected
    before ever reaching the subprocess."""
    violations: List[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ValidationResult(ok=False, violations=[f"Syntax error: {e}"])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if alias.name not in ALLOWED_IMPORTS and root not in {
                    m.split(".")[0] for m in ALLOWED_IMPORTS
                }:
                    violations.append(f"Disallowed import: '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            root = mod.split(".")[0]
            if mod not in ALLOWED_IMPORTS and root not in {
                m.split(".")[0] for m in ALLOWED_IMPORTS
            }:
                violations.append(f"Disallowed import: 'from {mod} import ...'")
        elif isinstance(node, ast.Attribute):
            if node.attr in _DANGEROUS_DUNDERS:
                violations.append(f"Disallowed attribute access: '.{node.attr}'")
        elif isinstance(node, ast.Name):
            if node.id in _DANGEROUS_DUNDERS:
                violations.append(f"Disallowed name reference: '{node.id}'")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in _DANGEROUS_CALL_NAMES:
                violations.append(f"Disallowed call: '{fn.id}(...)'")
            if isinstance(fn, ast.Attribute) and fn.attr in {"system", "popen", "spawn", "fork", "execv", "execve"}:
                violations.append(f"Disallowed call: '.{fn.attr}(...)'")

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    return ValidationResult(ok=len(unique) == 0, violations=unique)
