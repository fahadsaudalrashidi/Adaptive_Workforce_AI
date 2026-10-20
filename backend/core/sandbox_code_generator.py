"""
Sandbox Code Generator — Phase 43.

Generates the Python code the sandbox executes, from a natural-language
file-edit instruction. Uses this platform's EXISTING local Ollama
integration (same HTTP pattern as ai_business_analyst_engine.py's
_call_ollama), pointed at `qwen2.5-coder:7b` — a coding-specialized model
already installed on this machine — rather than the Anthropic/Claude API
the originating task brief assumed. There is no Anthropic SDK, no Claude
API key, and no cloud-LLM code anywhere in this codebase (confirmed before
writing this module — see PHASE_43_SANDBOXED_AGENT_REPORT.md's corrections
section). Using the platform's real, already-offline LLM keeps this
feature consistent with the rest of the platform's local-first
architecture instead of introducing a new cloud dependency that isn't
actually configured here — and means NO data (file structure, instruction,
or generated code) ever leaves the machine, a STRONGER data-locality
guarantee than the "cloud-mode disclosure" the brief asked the frontend to
show, which is why this build does not include one (see the frontend
changes for the corresponding note shown to the user instead).

IMPORTANT SEPARATION (Phase 43's Step 3 requirement): this module ONLY
ever produces code for the sandbox's mechanical file-editing execution. It
is never used to answer a factual/business question — that remains
ai_business_analyst_engine.py's answer_question()'s job, unchanged,
including its numeric guard. See sandbox_request_router.py for where a
mixed request ("edit this AND tell me why sales dropped") is split so each
half goes down its own architecturally distinct path.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from backend.core.ai_business_analyst_engine import OLLAMA_BASE_URL, OLLAMA_TIMEOUT_SECS

CODE_GEN_MODEL = "qwen2.5-coder:7b"

_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


@dataclass
class CodeGenResult:
    ok: bool
    code: Optional[str]
    raw_llm_response: Optional[str]
    error: Optional[str]


def code_gen_reachable() -> bool:
    """Same reachability check as ai_business_analyst_engine.ollama_reachable,
    duplicated locally so this module has no import-time dependency on
    which models happen to be pulled — only used to give an honest
    'code-generation backend unavailable' message rather than hanging."""
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                return False
            body = json.loads(resp.read().decode("utf-8"))
            models = {m.get("name") for m in body.get("models", [])}
            return CODE_GEN_MODEL in models
    except Exception:
        return False


def _build_prompt(instruction: str, file_structure_description: str, output_filename: str) -> str:
    return (
        "You are a Python code generator for a sandboxed file-editing tool. "
        "Given a user's instruction and the REAL structure of an uploaded file, "
        "write ONLY the Python code needed to perform the edit. "
        "Rules:\n"
        "- The sandboxed environment already provides these as pre-bound globals: "
        "`pd` (pandas), `np` (numpy), `openpyxl`, `docx` (python-docx), `pptx`/`Presentation` (python-pptx).\n"
        "- The input file is at the string constant `INPUT_PATH`. Write the result to `OUTPUT_PATH`.\n"
        f"- OUTPUT_PATH's extension will be '{output_filename.rsplit('.', 1)[-1]}' — write in that format.\n"
        "- Do NOT `import os`, `import sys`, `import subprocess`, `import socket`, or `import ctypes` — "
        "not needed and will be blocked.\n"
        "- Do NOT attempt any network access — there is none available.\n"
        "- Only reference files at INPUT_PATH/OUTPUT_PATH — no other file paths.\n"
        "- Output ONLY a single Python code block (```python ... ```) — no explanation before or after.\n\n"
        f"Real file structure:\n{file_structure_description}\n\n"
        f"User's instruction: {instruction}\n"
    )


def generate_edit_code(
    instruction: str,
    file_structure_description: str,
    output_filename: str,
    http_call: Optional[Callable[[str], Optional[str]]] = None,
) -> CodeGenResult:
    """
    Calls the local code-generation model and extracts a single Python code
    block from its response. `http_call` is injectable for tests (avoids
    depending on a live Ollama server for logic-only unit tests), mirroring
    ai_business_analyst_engine.phrase_with_ollama's testability pattern.
    """
    prompt = _build_prompt(instruction, file_structure_description, output_filename)
    caller = http_call or _call_code_gen_model

    try:
        raw = caller(prompt)
    except Exception as e:
        return CodeGenResult(ok=False, code=None, raw_llm_response=None, error=f"Code-generation call failed: {e}")

    if not raw:
        return CodeGenResult(
            ok=False, code=None, raw_llm_response=None,
            error="Code-generation backend (local Ollama, model "
                  f"'{CODE_GEN_MODEL}') returned no response — it may not be "
                  "running or the model may not be pulled.",
        )

    match = _CODE_FENCE_RE.search(raw)
    if not match:
        # Fall back to treating the whole response as code only if it looks
        # like Python and contains no prose — otherwise refuse rather than
        # guess wrong and hand malformed "code" to the sandbox.
        stripped = raw.strip()
        if stripped.startswith(("import ", "df", "pd.", "wb", "doc", "prs")):
            code = stripped
        else:
            return CodeGenResult(
                ok=False, code=None, raw_llm_response=raw,
                error="Code-generation model's response did not contain a "
                      "recognizable Python code block — refusing to guess.",
            )
    else:
        code = match.group(1).strip()

    if not code:
        return CodeGenResult(ok=False, code=None, raw_llm_response=raw, error="Extracted code block was empty.")

    return CodeGenResult(ok=True, code=code, raw_llm_response=raw, error=None)


def _call_code_gen_model(prompt: str) -> Optional[str]:
    payload = json.dumps({"model": CODE_GEN_MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate", data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
