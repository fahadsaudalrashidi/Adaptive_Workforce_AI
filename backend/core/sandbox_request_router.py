"""
Sandbox Request Router — Phase 43.

Splits a user's natural-language request into its FACTUAL/QUESTION
component (if any) and its FILE-EDIT/MUTATION component (if any), so each
half is routed down its own architecturally distinct path — the Phase 43
task's explicit Step 3 requirement: sandboxed code execution must never
become a backdoor for ungrounded business-fact claims.

  Question component  -> backend.core.ai_business_analyst_engine.answer_question()
                          (the existing Phase 37 registry + numeric-guard
                          discipline — completely unchanged by this phase)
  Edit component       -> backend.core.sandbox_code_generator +
                          backend.core.sandbox_executor
                          (this phase's new sandboxed execution path)

This module makes NO factual claims itself and calls no LLM — it is a
plain keyword/regex classifier over the user's own words, splitting on
sentence boundaries. Getting the split wrong in either direction is safe:
a question-like sentence that's actually just part of an edit instruction
still gets a harmless "unsupported question" answer from the existing
registry (never a fabricated fact); an edit-like sentence misclassified as
a question is simply not executed as code (fails safe, not open).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_EDIT_VERBS = re.compile(
    r"\b(edit|change|fix|update|correct|modify|add|remove|delete|insert|"
    r"rename|reformat|format|replace|set|adjust|clean|clean up|sort|filter|"
    r"recalculate|recompute|convert|merge|split|append|round|highlight|"
    r"color|bold|rewrite|translate|summarize into|extract)\b",
    re.IGNORECASE,
)

_QUESTION_TRIGGERS = re.compile(
    r"\b(why|what|how many|how much|which|who|when|explain|tell me|show me|"
    r"what is|what are|what was|what were)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\band\s+(?=(?:also\s+)?(?:tell|explain|why|what))")


@dataclass
class RequestSplit:
    question_part: str | None
    edit_part: str | None
    is_pure_question: bool
    is_pure_edit: bool
    is_mixed: bool
    is_ambiguous: bool  # neither an edit verb nor a question trigger found


def split_request(instruction: str) -> RequestSplit:
    instruction = (instruction or "").strip()
    if not instruction:
        return RequestSplit(None, None, False, False, False, True)

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(instruction) if s.strip()]
    if not sentences:
        sentences = [instruction]

    question_sentences: List[str] = []
    edit_sentences: List[str] = []

    for s in sentences:
        has_question = bool(_QUESTION_TRIGGERS.search(s))
        has_edit = bool(_EDIT_VERBS.search(s))
        if has_question and not has_edit:
            question_sentences.append(s)
        elif has_edit:
            edit_sentences.append(s)
        elif has_question:
            question_sentences.append(s)

    question_part = " ".join(question_sentences) or None
    edit_part = " ".join(edit_sentences) or None

    if not question_part and not edit_part:
        # Ambiguous — no clear verb/trigger. Treat the whole thing as a
        # candidate edit instruction (the more common case for this
        # endpoint), but flag it so the caller can be honest about the
        # uncertainty rather than silently guessing.
        return RequestSplit(None, instruction, False, True, False, True)

    return RequestSplit(
        question_part=question_part,
        edit_part=edit_part,
        is_pure_question=bool(question_part) and not edit_part,
        is_pure_edit=bool(edit_part) and not question_part,
        is_mixed=bool(question_part) and bool(edit_part),
        is_ambiguous=False,
    )
