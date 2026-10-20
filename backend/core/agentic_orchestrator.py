"""
Agentic Orchestrator — Phase 44.

Top-level entry point for the Claude-driven agent path. Deliberately a
NEW module, not an edit to ai_business_analyst_engine.py — that module's
answer_question() (the local-mode path) is byte-for-byte unchanged by this
phase, so local mode keeps working exactly as before for any user who
hasn't configured a cloud API key (the graceful-degradation requirement).

Extends Phase 37's numeric-guard discipline to a multi-tool-call agent
turn: every number in Claude's FINAL synthesized text must trace to a
real value returned by one of the tool calls made during this same turn
(VerifiedNumberPool, from agentic_tools.py) — exactly the same
tolerance-based check as ai_business_analyst_engine._numeric_guard_passes,
just checked against a pool accumulated across possibly several tool
calls instead of one Evidence Pack. If the check fails, Claude's prose is
discarded (never shown) and a plain, still-grounded listing of the real
tool outputs is returned instead — the agentic-path equivalent of Phase
37's deterministic-template fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.agentic_tools import (
    VerifiedNumberPool, GeneratedFile, all_tool_schemas,
    execute_get_business_metric, execute_get_variance_context,
    execute_generate_pptx_report, execute_merge_excel_files, execute_edit_file,
)
from backend.core.cloud_llm_client import call_claude_with_tools, ClaudeToolLoopResult


_SYSTEM_PROMPT = """You are a business analytics agent for the AI Business Analyst feature of an \
enterprise workforce/BI platform. You have tools to fetch REAL computed metrics from the \
user's own uploaded data, generate a real PowerPoint report, merge two uploaded Excel files, \
or edit an uploaded file.

HARD RULES — these are enforced by code after you respond, not just requested:
1. NEVER state a number in your final answer unless it came from a tool result you actually \
received in this conversation. A fabricated or estimated number will cause your ENTIRE answer \
to be discarded and replaced with a plain data listing — always call a tool first.
2. For "why did X happen" / causal questions: call get_variance_context first to get real \
period/category/department breakdowns. You may synthesize a data-grounded explanation (e.g. \
"expenses rose primarily in category Y, up N%, while other categories were flat") but you must \
NEVER introduce an external cause (market conditions, competitor actions, macroeconomic factors, \
seasonality) unless that specific factor is itself present in the tool data you received. If the \
data doesn't clearly point to a cause, say so honestly rather than guessing.
3. When generating a PPTX report, only include numbers you already fetched via a tool this turn — \
the tool itself will reject the request otherwise.
4. Keep your final answer concise and cite which real metric/period each figure came from."""


@dataclass
class AgenticActionTaken:
    tool_name: str
    tool_input: dict[str, Any]
    ok: bool
    summary: str


@dataclass
class AgenticAnswer:
    answer_text: str
    mode: str  # "claude_agent" | "claude_agent_fallback_ungrounded" | "error"
    actions_taken: list[AgenticActionTaken] = field(default_factory=list)
    files_generated: list[GeneratedFile] = field(default_factory=list)
    error: Optional[str] = None
    computed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def answer_with_claude_agent(
    question: str,
    domain_results: dict[str, Any],
    uploaded_frames: dict[str, pd.DataFrame],
    uploaded_file_bytes: dict[str, bytes],
    api_call: Optional[Any] = None,
) -> AgenticAnswer:
    pool = VerifiedNumberPool()
    files_generated: list[GeneratedFile] = []
    actions: list[AgenticActionTaken] = []

    def tool_executor(tool_name: str, tool_input: dict[str, Any]) -> Any:
        if tool_name == "get_business_metric":
            result = execute_get_business_metric(tool_input["query_id"], domain_results, pool)
            actions.append(AgenticActionTaken(
                tool_name, tool_input, result.get("available", False),
                f"Fetched '{tool_input.get('query_id')}'" + ("" if result.get("available") else f" — unavailable: {result.get('reason')}"),
            ))
            return result

        if tool_name == "get_variance_context":
            result = execute_get_variance_context(tool_input["domain"], domain_results, pool)
            actions.append(AgenticActionTaken(
                tool_name, tool_input, result.get("available", False),
                f"Fetched variance context for '{tool_input.get('domain')}'" + ("" if result.get("available") else f" — unavailable: {result.get('reason')}"),
            ))
            return result

        if tool_name == "generate_pptx_report":
            result = execute_generate_pptx_report(tool_input.get("title", ""), tool_input.get("sections", []), pool)
            ok = bool(result.get("ok"))
            if ok and result.get("file"):
                files_generated.append(result["file"])
                actions.append(AgenticActionTaken(tool_name, tool_input, True, f"Generated PPTX '{result['file'].filename}' ({result.get('n_slides')} slides)"))
                return {"ok": True, "filename": result["file"].filename, "n_slides": result.get("n_slides")}
            actions.append(AgenticActionTaken(tool_name, tool_input, False, result.get("error", "PPTX generation failed")))
            return result

        if tool_name == "merge_excel_files":
            result = execute_merge_excel_files(
                tool_input["left_filename"], tool_input["right_filename"],
                tool_input["on_column"], tool_input["how"], uploaded_frames, pool,
            )
            ok = bool(result.get("ok"))
            if ok and result.get("file"):
                files_generated.append(result["file"])
                actions.append(AgenticActionTaken(tool_name, tool_input, True, f"Merged into '{result['file'].filename}' ({result['n_rows']} rows x {result['n_columns']} cols)"))
                return {"ok": True, "filename": result["file"].filename, "n_rows": result["n_rows"], "n_columns": result["n_columns"], "columns": result["columns"]}
            actions.append(AgenticActionTaken(tool_name, tool_input, False, result.get("error", "Merge failed")))
            return result

        if tool_name == "edit_file":
            result = execute_edit_file(tool_input["filename"], tool_input["instruction"], uploaded_file_bytes)
            ok = bool(result.get("ok"))
            if ok and result.get("file"):
                files_generated.append(result["file"])
                diff = result.get("diff_summary") or {}
                actions.append(AgenticActionTaken(tool_name, tool_input, True, f"Edited '{result['file'].filename}': {diff.get('summary_en', 'edit applied')}"))
                return {"ok": True, "filename": result["file"].filename, "diff_summary": result.get("diff_summary")}
            actions.append(AgenticActionTaken(tool_name, tool_input, False, result.get("error", "Sandboxed edit failed")))
            return result

        raise ValueError(f"Unknown tool: {tool_name}")

    loop_result: ClaudeToolLoopResult = call_claude_with_tools(
        system_prompt=_SYSTEM_PROMPT, user_message=question,
        tools=all_tool_schemas(), tool_executor=tool_executor, api_call=api_call,
    )

    if loop_result.error and loop_result.final_text is None:
        return AgenticAnswer(
            answer_text=f"The cloud agent could not complete this request: {loop_result.error}",
            mode="error", actions_taken=actions, files_generated=files_generated, error=loop_result.error,
        )

    final_text = loop_result.final_text or ""
    ok, untraceable = pool.text_is_grounded(final_text)

    if ok and final_text:
        return AgenticAnswer(answer_text=final_text, mode="claude_agent", actions_taken=actions, files_generated=files_generated)

    # Numeric guard failed (or Claude returned no text) — fall back to a
    # plain, still-grounded listing of the real tool outputs. Never show
    # the ungrounded prose.
    fallback = _build_grounded_fallback(actions, untraceable if not ok else [])
    return AgenticAnswer(
        answer_text=fallback, mode="claude_agent_fallback_ungrounded",
        actions_taken=actions, files_generated=files_generated,
        error=(f"Discarded the model's phrased answer — it contained number(s) {untraceable} not traceable to any tool result." if not ok and final_text else None),
    )


def _build_grounded_fallback(actions: list[AgenticActionTaken], untraceable: list[str]) -> str:
    if not actions:
        return "No data could be fetched to answer this question — no registered metric or variance context matched."
    lines = ["Here is what was actually fetched (shown plainly because the phrased answer could not be fully verified):"]
    for a in actions:
        lines.append(f"- {a.summary}")
    return "\n".join(lines)
