"""
Cloud LLM Client — Phase 44 (this session's real, verified prior phase is
Phase 43's sandboxed code execution — see PHASE_43_SANDBOXED_AGENT_REPORT.md
— not the "Phase 42" the originating task brief assumed; see
PHASE_44_AGENTIC_AI_ANALYST_REPORT.md's corrections section).

Wraps the real Anthropic API for the AI Business Analyst's agentic
tool-use path. This is an EXPLICIT, USER-CONFIRMED, SCOPED exception to
this platform's offline-first architecture (see
backend/core/offline_mode_guard.py, which remains fully active and
unaffected — every other module continues to have zero network access;
only this one client, only when ANTHROPIC_API_KEY is set, ever calls out).

Architectural role, mirrored against the existing local-LLM path in
ai_business_analyst_engine.py:
  - _call_ollama() -> phrase_with_ollama(): the local model REPHRASES an
    already-computed deterministic answer; it never chooses which data to
    fetch. There was no LLM-driven tool-selection in this codebase before
    Phase 44 — classify_intent()/match_registry_entry() (pure keyword
    matching) did that job.
  - call_claude_with_tools() (this module): Claude's real tool-use
    capability now does that selection itself, choosing from a small,
    explicit set of registered tools (backend/core/agentic_tools.py) —
    but every tool it can call is still one of: (a) a fixed, pre-registered
    query-registry function (backend/core/ai_business_analyst_engine.py's
    run_registered_query — completely unchanged), (b) the new PPTX/merge
    tools (deterministic, non-LLM Python), or (c) the Phase 43 sandbox
    (already-adversarially-tested, unmodified at the execution layer).
    Claude never gets a raw code-execution tool of its own — "sandboxed
    file edit" is a fixed tool whose OWN internal implementation happens to
    call the code-generation model, not something Claude can bypass to run
    arbitrary code directly.

Numeric-guard discipline is extended, not replaced — see
answer_with_claude() in ai_business_analyst_engine.py's Phase 44 addition
for where every number in Claude's final synthesized text is checked
against the real tool-result values collected during the loop, exactly the
same tolerance-based check as _numeric_guard_passes() for the local model.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from config.settings import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

_STATUS_CACHE_TTL_SECS = 60.0
_status_cache: dict[str, Any] = {"checked_at": 0.0, "result": None}


def mask_api_key(key: str) -> str:
    """First 8 + last 4 characters only — the convention used everywhere
    this key might need to appear in a log, status response, or report."""
    if not key or len(key) < 16:
        return "(not configured)"
    return f"{key[:8]}...{key[-4:]}"


@dataclass
class CloudModeStatus:
    configured: bool          # ANTHROPIC_API_KEY is set (non-empty)
    valid: bool                # a real minimal API call succeeded
    detail: str                # honest, specific reason (e.g. "credit balance too low", not just "unavailable")
    masked_key: str
    model: str
    checked_at: float = field(default_factory=time.time)


def check_cloud_mode(force: bool = False, http_call: Optional[Callable[[], Any]] = None) -> CloudModeStatus:
    """
    Real validation, not a file-existence check — makes an actual minimal
    API call (cached for _STATUS_CACHE_TTL_SECS so the frontend can poll
    this without hammering Anthropic's API on every render). `http_call` is
    injectable for tests, mirroring the exact pattern already established
    by ai_business_analyst_engine.phrase_with_ollama's `http_call` param.
    """
    global _status_cache
    now = time.time()
    if not force and _status_cache["result"] is not None and (now - _status_cache["checked_at"]) < _STATUS_CACHE_TTL_SECS:
        return _status_cache["result"]

    masked = mask_api_key(ANTHROPIC_API_KEY)

    if not ANTHROPIC_API_KEY:
        result = CloudModeStatus(
            configured=False, valid=False,
            detail="No ANTHROPIC_API_KEY configured — local Ollama mode only.",
            masked_key=masked, model=ANTHROPIC_MODEL,
        )
        _status_cache = {"checked_at": now, "result": result}
        return result

    try:
        if http_call is not None:
            http_call()
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            client.messages.create(
                model=ANTHROPIC_MODEL, max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        result = CloudModeStatus(
            configured=True, valid=True, detail="Anthropic API reachable and key validated.",
            masked_key=masked, model=ANTHROPIC_MODEL,
        )
    except Exception as exc:
        # Deliberately distinguish "key present but currently non-functional"
        # (e.g. billing/credit issues, rate limits) from "not configured at
        # all" — both fall back to local mode operationally, but the
        # diagnostic shown to the user must be honest about which one it is
        # rather than a generic "unavailable". A real run against this
        # project's own configured key hit exactly this path — see
        # PHASE_44_AGENTIC_AI_ANALYST_REPORT.md.
        detail = _classify_anthropic_error(exc)
        result = CloudModeStatus(
            configured=True, valid=False, detail=detail,
            masked_key=masked, model=ANTHROPIC_MODEL,
        )

    _status_cache = {"checked_at": now, "result": result}
    return result


def _classify_anthropic_error(exc: Exception) -> str:
    msg = str(exc)
    if "credit balance" in msg.lower():
        return "Key is valid (authenticated), but the Anthropic account's credit balance is too low to make requests."
    if "authentication" in msg.lower() or "401" in msg or "invalid x-api-key" in msg.lower() or "invalid_api_key" in msg.lower():
        return "Key is present but invalid/rejected by Anthropic (authentication failed)."
    if "rate limit" in msg.lower() or "429" in msg:
        return "Key is valid, but currently rate-limited."
    return f"Anthropic API call failed: {msg[:200]}"


@dataclass
class ToolCallRequest:
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str


@dataclass
class ClaudeToolLoopResult:
    final_text: Optional[str]
    tool_calls_made: list[ToolCallRequest]
    tool_results: list[dict[str, Any]]  # {"tool_name", "tool_use_id", "output"} — every real value returned, for the numeric guard
    stopped_reason: str  # "end_turn" | "max_iterations" | "error"
    error: Optional[str] = None


def call_claude_with_tools(
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]],
    tool_executor: Callable[[str, dict[str, Any]], Any],
    max_iterations: int = 5,
    api_call: Optional[Callable[..., Any]] = None,
) -> ClaudeToolLoopResult:
    """
    Runs the real Claude tool-use loop: send the message + tool schemas,
    execute whatever tools Claude actually requests (via `tool_executor` —
    always one of the fixed registered functions, never free code), feed
    results back, repeat until Claude stops requesting tools or
    `max_iterations` is hit.

    `api_call` is injectable for tests: a callable taking the same kwargs
    as `anthropic.Anthropic().messages.create(...)` and returning a
    duck-typed response object (`.content` list of blocks with `.type`,
    `.text`/`.name`/`.input`/`.id`, `.stop_reason`) — lets tool-loop logic
    be verified without a live, billed API call.
    """
    if api_call is None:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        api_call = client.messages.create

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    all_tool_calls: list[ToolCallRequest] = []
    all_tool_results: list[dict[str, Any]] = []

    for _ in range(max_iterations):
        try:
            response = api_call(
                model=ANTHROPIC_MODEL, max_tokens=2048,
                system=system_prompt, messages=messages, tools=tools,
            )
        except Exception as exc:
            return ClaudeToolLoopResult(
                final_text=None, tool_calls_made=all_tool_calls, tool_results=all_tool_results,
                stopped_reason="error", error=_classify_anthropic_error(exc),
            )

        tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        text_blocks = [b for b in response.content if getattr(b, "type", None) == "text"]

        if not tool_use_blocks:
            final_text = "\n".join(b.text for b in text_blocks) if text_blocks else None
            return ClaudeToolLoopResult(
                final_text=final_text, tool_calls_made=all_tool_calls, tool_results=all_tool_results,
                stopped_reason="end_turn",
            )

        # Assistant turn requested tool(s) — execute each for real, append
        # the assistant message + our tool_result messages, loop again.
        messages.append({"role": "assistant", "content": response.content})
        tool_result_content = []
        for block in tool_use_blocks:
            req = ToolCallRequest(tool_name=block.name, tool_input=block.input, tool_use_id=block.id)
            all_tool_calls.append(req)
            try:
                output = tool_executor(block.name, block.input)
                all_tool_results.append({"tool_name": block.name, "tool_use_id": block.id, "output": output})
                tool_result_content.append({
                    "type": "tool_result", "tool_use_id": block.id, "content": _stringify_tool_output(output),
                })
            except Exception as exc:
                tool_result_content.append({
                    "type": "tool_result", "tool_use_id": block.id,
                    "content": f"Tool execution error: {exc}", "is_error": True,
                })
        messages.append({"role": "user", "content": tool_result_content})

    return ClaudeToolLoopResult(
        final_text=None, tool_calls_made=all_tool_calls, tool_results=all_tool_results,
        stopped_reason="max_iterations",
        error=f"Exceeded {max_iterations} tool-use iterations without a final answer.",
    )


def _stringify_tool_output(output: Any) -> str:
    import json
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, default=str)
    except (TypeError, ValueError):
        return str(output)
