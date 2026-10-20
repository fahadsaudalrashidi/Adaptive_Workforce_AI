"""
Agentic Tools — Phase 44.

The explicit, bounded set of tools the Claude-driven agent may invoke.
Every tool here is one of exactly three kinds — never free code:

  1. get_business_metric / get_variance_context — thin wrappers around
     backend/core/ai_business_analyst_engine.py's EXISTING, unmodified
     run_registered_query() / domain analyzers. Claude picks a query_id
     from a closed enum (the tool schema's `enum` list, built from the
     real QUERY_REGISTRY keys) — it cannot invent a new one; an unknown
     ID raises KeyError inside run_registered_query() itself, "the ONLY
     function permitted to execute a registry entry" (that module's own
     docstring, unchanged by this phase).
  2. generate_pptx_report / merge_excel_files — new, but deterministic,
     non-LLM Python (python-pptx / pandas). Claude supplies structured
     JSON input (a title, section list, sheet names); the tool itself
     does no reasoning and generates no numbers of its own — see
     _NumberGuard below for how a fabricated number in the REQUESTED
     content is caught before a slide/cell is ever written.
  3. edit_file — a thin wrapper around Phase 43's ALREADY-BUILT,
     adversarially-tested sandbox (backend/core/sandbox_executor.py +
     sandbox_code_generator.py + sandbox_diff_summary.py). Nothing about
     the sandbox itself changes here — Claude is simply a second caller
     of the exact same, unmodified execution path the local model already
     used in Phase 43. The instruction still goes through code generation
     and the same 3-layer isolation; Claude never gets to submit code
     directly.

Reconciling this with Phase 37's "dispatch is never LLM-driven" rule
(ai_business_analyst_engine.py's module docstring): that rule was about
UNBOUNDED free-form dispatch — an LLM's raw text output directly choosing
what code runs, with no structural limit on what it could pick or invent.
Claude's tool-use is schema-constrained to this exact, small, closed set
of pre-vetted actions; it cannot call anything not defined here, and
every metric-fetching tool still routes through the exact same
`run_registered_query()` gate Phase 37 built. What changes is WHICH
mechanism picks a tool from a fixed menu (keyword-matching vs. Claude's
structured tool selection) — not whether arbitrary computation becomes
reachable, which it does not.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import pandas as pd

from backend.core.ai_business_analyst_engine import (
    QUERY_REGISTRY, run_registered_query, QueryOutcome, ComputedMetricEvidence,
    analyze_financial_intelligence,
)


# ── Numeric guard for tool-generated FILE content (not just final chat text) ──
# Extends Phase 37's numeric-guard discipline to the two content-generating
# tools: a number Claude asks to put in a PPTX slide or (implicitly, since
# merge is a real pandas op with no invented numbers) must be traceable to
# a REAL value returned by an earlier tool call in this same session — not
# just plausible-sounding. This is the file-generation analog of
# ai_business_analyst_engine._numeric_guard_passes().

import re as _re
_NUMBER_RE = _re.compile(r"-?\d[\d,]*\.?\d*")


def _normalize_num(s: str) -> str:
    try:
        return f"{float(s.replace(',', '')):.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return s


def _numbers_close(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < max(0.01, abs(float(b)) * 0.005)
    except (TypeError, ValueError):
        return a == b


@dataclass
class VerifiedNumberPool:
    """Accumulates every real value returned by tool calls during one agent
    turn — both NUMERIC values (for the number-traceability guard) and
    non-numeric STRING values like period labels ("2026-02") or category
    names, which the guard must NOT flag as untraceable numbers just
    because they contain digits. A real bug caught this: a genuinely
    grounded causal narrative that says "...from 2026-01 to 2026-02..."
    (both real period labels returned by get_variance_context) was
    initially rejected, because the digit-matching regex extracted "2026",
    "01", "02" as if they were separate invented numbers with no tool
    evidence behind them. Fixed by masking out every known-real string
    span BEFORE running the numeric regex, so its embedded digits are
    never examined at all."""
    values: list[str] = field(default_factory=list)
    known_strings: list[str] = field(default_factory=list)

    def add_from_outcome(self, outcome: QueryOutcome) -> None:
        for m in outcome.metrics:
            if isinstance(m.value, (int, float)):
                self.values.append(_normalize_num(str(m.value)))
            elif isinstance(m.value, str) and m.value:
                self.known_strings.append(m.value)

    def add_raw(self, value: Any) -> None:
        if isinstance(value, (int, float)):
            self.values.append(_normalize_num(str(value)))
        elif isinstance(value, str) and value:
            self.known_strings.append(value)

    def text_is_grounded(self, text: str) -> tuple[bool, list[str]]:
        """Returns (ok, untraceable_numbers)."""
        masked_text = text
        # Longest strings first, so a longer real value (e.g. a full
        # category name) is masked before any shorter substring of it could
        # coincidentally be re-matched.
        for s in sorted(set(self.known_strings), key=len, reverse=True):
            if s:
                masked_text = masked_text.replace(s, " " * len(s))

        untraceable = []
        for match in _NUMBER_RE.findall(masked_text):
            candidate = _normalize_num(match)
            if candidate in ("", "-", "."):
                continue
            if not any(_numbers_close(candidate, v) for v in self.values):
                untraceable.append(match)
        return (len(untraceable) == 0, untraceable)


# ── Tool 1: get_business_metric ─────────────────────────────────────────────

def get_business_metric_tool_schema() -> dict[str, Any]:
    return {
        "name": "get_business_metric",
        "description": (
            "Fetch ONE real, pre-computed business metric from this platform's "
            "verified query registry. This is the ONLY way to get a real number — "
            "never state a business figure without calling this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "enum": sorted(QUERY_REGISTRY.keys()),
                    "description": "The exact registered query ID to fetch.",
                },
            },
            "required": ["query_id"],
        },
    }


def execute_get_business_metric(query_id: str, domain_results: dict[str, Any], pool: VerifiedNumberPool) -> dict[str, Any]:
    try:
        outcome = run_registered_query(query_id, domain_results)
    except KeyError as e:
        return {"available": False, "reason": str(e)}
    if not outcome.available:
        return {"available": False, "reason": outcome.reason}
    pool.add_from_outcome(outcome)
    return {
        "available": True,
        "source_engine": outcome.source_engine,
        "data_period": outcome.data_period,
        "metrics": [
            {"label": m.label, "value": m.value, "unit": m.unit, "evidence_level": m.evidence_level}
            for m in outcome.metrics
        ],
    }


# ── Tool 2: get_variance_context (Step 2 — richer causal-analysis bundle) ──

def get_variance_context_tool_schema() -> dict[str, Any]:
    return {
        "name": "get_variance_context",
        "description": (
            "Fetch a RICH multi-metric evidence bundle for causal/'why did X change' "
            "questions — real period-over-period variance, real category breakdowns, "
            "and real department breakdowns, all from the same uploaded data. Use this "
            "BEFORE attempting to explain WHY a metric changed; never guess a cause "
            "without this real breakdown data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "enum": ["financial"],
                    "description": "Which domain's variance context to fetch. Only 'financial' has period-variance + category/department breakdown data currently wired.",
                },
            },
            "required": ["domain"],
        },
    }


def execute_get_variance_context(domain: str, domain_results: dict[str, Any], pool: VerifiedNumberPool) -> dict[str, Any]:
    if domain != "financial":
        return {"available": False, "reason": f"No variance context available for domain '{domain}'."}
    fi = domain_results.get("financial")
    if fi is None:
        return {"available": False, "reason": "No financial data available in this session's uploaded file(s)."}

    def _round(v: Optional[float]) -> Optional[float]:
        return round(v, 2) if isinstance(v, (int, float)) else v

    period_variances = [
        {
            "period": v.period, "prior_period": v.prior_period,
            "revenue_variance_pct": _round(v.revenue_variance_pct),
            "expense_variance_pct": _round(v.expense_variance_pct),
            "net_variance_sar": _round(v.net_variance_sar),
        }
        for v in fi.period_variances
    ]
    revenue_by_category = [
        {"category": c.category, "total_sar": _round(c.total_sar), "share_pct": _round(c.share_pct)}
        for c in fi.revenue_by_category
    ]
    expense_by_category = [
        {"category": c.category, "total_sar": _round(c.total_sar), "share_pct": _round(c.share_pct)}
        for c in fi.expense_by_category
    ]
    expense_by_department = [
        {"department": d.department, "total_expense_sar": _round(d.total_expense_sar)}
        for d in fi.expense_by_department
    ]

    for bundle in (period_variances, revenue_by_category, expense_by_category, expense_by_department):
        for row in bundle:
            for v in row.values():
                pool.add_raw(v)

    return {
        "available": True,
        "source_engine": "financial_intelligence_reporting_engine.analyze_financial_intelligence",
        "period_variances": period_variances,
        "revenue_by_category": revenue_by_category,
        "expense_by_category": expense_by_category,
        "expense_by_department": expense_by_department,
        "governance_note": (
            "This is real transaction data from the uploaded file's own categorization. "
            "Any causal narrative built from this must stay traceable to these figures — "
            "never introduce an external cause (market conditions, competitor actions, "
            "macroeconomic factors) that isn't itself present in this data."
        ),
    }


# ── Tool 3: generate_pptx_report ────────────────────────────────────────────

def generate_pptx_report_tool_schema() -> dict[str, Any]:
    return {
        "name": "generate_pptx_report",
        "description": (
            "Generate a real PowerPoint file from real, already-fetched evidence. "
            "Every number in `sections` MUST have come from a prior get_business_metric "
            "or get_variance_context call in this same conversation — a number that "
            "doesn't trace back to a real tool result will be rejected and the file "
            "will NOT be generated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "bullets": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["heading", "bullets"],
                    },
                },
            },
            "required": ["title", "sections"],
        },
    }


@dataclass
class GeneratedFile:
    filename: str
    content_bytes: bytes
    content_type: str


def execute_generate_pptx_report(title: str, sections: list[dict[str, Any]], pool: VerifiedNumberPool) -> dict[str, Any]:
    all_text = title + " " + " ".join(
        s.get("heading", "") + " " + " ".join(s.get("bullets", [])) for s in sections
    )
    ok, untraceable = pool.text_is_grounded(all_text)
    if not ok:
        return {
            "ok": False,
            "error": f"Rejected: number(s) {untraceable} in the requested slide content do not trace to any "
                     f"real value fetched via get_business_metric/get_variance_context this session. "
                     f"Fetch the real figure first, then retry.",
        }

    from pptx import Presentation
    from pptx.util import Inches, Pt

    prs = Presentation()
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_slide.shapes.title.text = title
    if len(title_slide.placeholders) > 1:
        title_slide.placeholders[1].text = "Generated by AI Business Analyst — every figure traced to verified data"

    for section in sections:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = section.get("heading", "")
        body = slide.placeholders[1].text_frame
        bullets = section.get("bullets", [])
        if bullets:
            body.text = bullets[0]
            for b in bullets[1:]:
                p = body.add_paragraph()
                p.text = b

    buf = io.BytesIO()
    prs.save(buf)
    return {
        "ok": True,
        "file": GeneratedFile(
            filename=f"{_safe_filename(title)}.pptx",
            content_bytes=buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        "n_slides": len(sections) + 1,
    }


def _safe_filename(s: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in " _-" else "" for c in s).strip()
    return (cleaned or "report").replace(" ", "_")[:80]


# ── Tool 4: merge_excel_files ────────────────────────────────────────────────
# Deliberately a FIXED, deterministic pandas operation — NOT routed through
# the Phase 43 sandbox. Reasoning: "merge these two files on a key column"
# is a single, unambiguous, well-defined operation with no room for varied
# interpretation the way a free-form "clean this up" edit instruction has —
# it doesn't benefit from LLM code generation, and a fixed function is
# faster, fully deterministic, and trivially auditable (no generated code to
# review at all). The Phase 43 sandbox remains the right tool for genuinely
# open-ended edit instructions (see execute_edit_file below), which this is
# not.

def merge_excel_files_tool_schema() -> dict[str, Any]:
    return {
        "name": "merge_excel_files",
        "description": (
            "Merge two already-uploaded files on a shared key column using a real, "
            "deterministic pandas merge (inner/left/right/outer). Returns a real "
            "row/column count for the result — never estimated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "left_filename": {"type": "string"},
                "right_filename": {"type": "string"},
                "on_column": {"type": "string"},
                "how": {"type": "string", "enum": ["inner", "left", "right", "outer"]},
            },
            "required": ["left_filename", "right_filename", "on_column", "how"],
        },
    }


def execute_merge_excel_files(
    left_filename: str, right_filename: str, on_column: str, how: str,
    uploaded_frames: dict[str, pd.DataFrame], pool: VerifiedNumberPool,
) -> dict[str, Any]:
    if left_filename not in uploaded_frames:
        return {"ok": False, "error": f"'{left_filename}' was not uploaded in this session."}
    if right_filename not in uploaded_frames:
        return {"ok": False, "error": f"'{right_filename}' was not uploaded in this session."}
    left = uploaded_frames[left_filename]
    right = uploaded_frames[right_filename]
    if on_column not in left.columns:
        return {"ok": False, "error": f"Column '{on_column}' not found in '{left_filename}'. Columns: {list(left.columns)}"}
    if on_column not in right.columns:
        return {"ok": False, "error": f"Column '{on_column}' not found in '{right_filename}'. Columns: {list(right.columns)}"}

    merged = left.merge(right, on=on_column, how=how, suffixes=("_left", "_right"))
    pool.add_raw(len(merged))
    pool.add_raw(len(merged.columns))

    buf = io.BytesIO()
    merged.to_excel(buf, index=False)
    return {
        "ok": True,
        "n_rows": len(merged),
        "n_columns": len(merged.columns),
        "columns": list(merged.columns),
        "file": GeneratedFile(
            filename=f"merged_{Path(left_filename).stem}_{Path(right_filename).stem}.xlsx",
            content_bytes=buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    }


# ── Tool 5: edit_file — wraps the Phase 43 sandbox, UNMODIFIED ─────────────

def edit_file_tool_schema() -> dict[str, Any]:
    return {
        "name": "edit_file",
        "description": (
            "Edit an already-uploaded file per a natural-language instruction. Runs in "
            "an isolated sandbox (no network, filesystem confined to a temp copy, hard "
            "resource limits) — the exact same sandbox already adversarially tested. "
            "Use this for open-ended edits, not for a simple two-file merge (use "
            "merge_excel_files for that)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "instruction": {"type": "string"},
            },
            "required": ["filename", "instruction"],
        },
    }


def execute_edit_file(
    filename: str, instruction: str, uploaded_file_bytes: dict[str, bytes],
) -> dict[str, Any]:
    from backend.core.sandbox_file_structure import describe_file_structure
    from backend.core.sandbox_code_generator import generate_edit_code
    from backend.core.sandbox_executor import run_sandboxed_code, cleanup_sandbox_run
    from backend.core.sandbox_diff_summary import compute_diff_summary

    if filename not in uploaded_file_bytes:
        return {"ok": False, "error": f"'{filename}' was not uploaded in this session."}
    raw = uploaded_file_bytes[filename]
    structure = describe_file_structure(raw, filename)
    stem, suffix = Path(filename).stem, Path(filename).suffix
    output_filename = f"{stem}_edited{suffix}"

    gen = generate_edit_code(instruction, structure, output_filename)
    if not gen.ok:
        return {"ok": False, "error": gen.error}

    result = run_sandboxed_code(gen.code, raw, filename, output_filename, "local", instruction)
    if result.outcome != "success" or result.output_file_path is None:
        cleanup_sandbox_run(result.run_id)
        return {"ok": False, "error": result.exit_reason or "Sandboxed edit did not complete successfully."}

    input_copy_path = result.output_file_path.parent / filename
    try:
        diff = compute_diff_summary(input_copy_path, result.output_file_path)
        diff_dict = {"changed": diff.changed, "summary_en": diff.summary_en}
    except Exception:
        diff_dict = None
    output_bytes = result.output_file_path.read_bytes()
    cleanup_sandbox_run(result.run_id)

    content_type = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".csv": "text/csv",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }.get(suffix.lower(), "application/octet-stream")

    return {
        "ok": True,
        "diff_summary": diff_dict,
        "generated_code": gen.code,
        "file": GeneratedFile(filename=output_filename, content_bytes=output_bytes, content_type=content_type),
    }


def all_tool_schemas() -> list[dict[str, Any]]:
    return [
        get_business_metric_tool_schema(),
        get_variance_context_tool_schema(),
        generate_pptx_report_tool_schema(),
        merge_excel_files_tool_schema(),
        edit_file_tool_schema(),
    ]
