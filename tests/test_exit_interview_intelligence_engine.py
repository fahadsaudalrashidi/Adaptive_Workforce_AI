"""
Phase 35.3 — Exit Interview / Free-Text Intelligence Engine tests.

Covers: theme classification against the reused theory-construct taxonomy,
evidence-strength labeling, TF-IDF/word-frequency term extraction, the
small-sample governance floor, and — critically — that raw PII (emails,
phone numbers, national IDs) and raw response text never reach the output.

Run: py -m pytest tests/test_exit_interview_intelligence_engine.py -v
"""

from __future__ import annotations

import pytest

from backend.core.exit_interview_intelligence_engine import (
    EVIDENCE_DIRECT,
    EVIDENCE_STRONG_PROXY,
    MIN_DOCUMENT_FREQUENCY,
    MIN_RESPONSES_FOR_AGGREGATE,
    THEME_KEYWORDS,
    analyze_exit_interview_text,
    exit_interview_intelligence_to_dict,
    unavailable_exit_interview_result,
)


def _overtime_heavy_corpus(n: int = 6) -> list[str]:
    phrasings = [
        "Too much overtime, I was constantly exhausted.",
        "Unpaid overtime every single week wore me down.",
        "Excessive overtime made it impossible to have a life.",
        "Mandatory overtime with no notice was the final straw.",
        "Forced overtime on weekends became normal here.",
        "Too much overtime every single sprint, I had to leave.",
    ]
    return phrasings[:n]


# ── Governance floor: minimum responses ─────────────────────────────────────

def test_unavailable_with_no_responses():
    result = analyze_exit_interview_text([])
    assert result.available is False
    assert result.theme_frequencies == []


def test_unavailable_below_minimum_response_count():
    responses = _overtime_heavy_corpus(MIN_RESPONSES_FOR_AGGREGATE - 1)
    result = analyze_exit_interview_text(responses)
    assert result.available is False
    assert str(MIN_RESPONSES_FOR_AGGREGATE) in result.reason


def test_available_at_exactly_minimum_response_count():
    responses = _overtime_heavy_corpus(MIN_RESPONSES_FOR_AGGREGATE)
    result = analyze_exit_interview_text(responses)
    assert result.available is True
    assert result.n_responses_analyzed == MIN_RESPONSES_FOR_AGGREGATE


def test_empty_and_whitespace_responses_are_dropped_before_count_check():
    responses = _overtime_heavy_corpus(5) + ["", "   ", None]  # type: ignore[list-item]
    result = analyze_exit_interview_text(responses)
    assert result.n_responses_total == 8
    assert result.n_responses_analyzed == 5


# ── Theme classification (reuses the SAME construct taxonomy) ──────────────

def test_overtime_theme_detected_with_direct_evidence():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    assert result.available is True
    themes = {t.construct: t for t in result.theme_frequencies}
    assert "Overtime Demand" in themes
    assert themes["Overtime Demand"].theory_anchor == "JD-R"
    assert themes["Overtime Demand"].direction == "risk"
    assert themes["Overtime Demand"].evidence_strength == EVIDENCE_DIRECT
    assert themes["Overtime Demand"].n_responses_mentioned == 6


def test_theme_taxonomy_matches_theory_construct_names():
    """Every theme construct name must be a real, intentional reuse of the
    established theory taxonomy (JD-R/COR/Equity/Mobley/FFM), not invented."""
    valid_theories = {"JD-R", "COR", "Equity", "Mobley", "FFM"}
    for construct, spec in THEME_KEYWORDS.items():
        assert spec["theory"] in valid_theories, f"{construct} uses an unrecognised theory anchor"
        assert spec["direction"] in ("risk", "protective")


def test_proxy_phrase_yields_strong_proxy_not_direct_evidence():
    responses = [
        "I was overworked and never had time off, it was too much.",
        "Working late every night, no time off at all for weeks.",
        "Overworked constantly, no time off ever given to me.",
        "It felt like I was overworked with no time off in sight.",
        "Never had time off, always overworked beyond reason.",
    ]
    result = analyze_exit_interview_text(responses)
    themes = {t.construct: t for t in result.theme_frequencies}
    assert "Overtime Demand" in themes
    assert themes["Overtime Demand"].evidence_strength == EVIDENCE_STRONG_PROXY


def test_themes_below_min_document_frequency_are_suppressed():
    """A theme mentioned by fewer than MIN_DOCUMENT_FREQUENCY respondents
    must not appear in the output at all, even if the corpus is large enough."""
    responses = _overtime_heavy_corpus(5) + [
        "I loved my job here, it was a great place to work overall.",
    ]
    result = analyze_exit_interview_text(responses)
    themes = {t.construct for t in result.theme_frequencies}
    # "Job Satisfaction" mentioned by only 1 respondent — below MIN_DOCUMENT_FREQUENCY=3.
    assert "Job Satisfaction" not in themes


def test_multiple_themes_ranked_by_frequency_descending():
    responses = _overtime_heavy_corpus(6) + [
        "Underpaid and unfair pay compared to the market rate here.",
        "The pay was too low, unfair pay across the whole team.",
        "Unfair pay was the main reason, I felt underpaid daily.",
    ]
    result = analyze_exit_interview_text(responses)
    counts = [t.n_responses_mentioned for t in result.theme_frequencies]
    assert counts == sorted(counts, reverse=True)


# ── PII / privacy guarantees ─────────────────────────────────────────────────

def test_raw_response_text_never_appears_in_serialized_output():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    d = exit_interview_intelligence_to_dict(result)
    serialized = str(d)
    for r in responses:
        assert r not in serialized, "raw response text leaked into serialized output"


def test_email_and_phone_are_scrubbed_and_never_surface_as_terms():
    responses = _overtime_heavy_corpus(5) + [
        "Contact me at exiting.employee@example.com or 0551234567 for details about overtime.",
    ]
    result = analyze_exit_interview_text(responses)
    d = exit_interview_intelligence_to_dict(result)
    serialized = str(d).lower()
    assert "exiting.employee" not in serialized
    assert "example.com" not in serialized
    assert "0551234567" not in serialized


def test_one_off_identifying_detail_does_not_reach_min_document_frequency():
    """A term mentioned by only 1 respondent (e.g. a name-like token) must
    never surface in top_terms, since MIN_DOCUMENT_FREQUENCY requires >=3
    distinct responses to contain it."""
    responses = _overtime_heavy_corpus(6) + [
        "My supervisor Alexandra Whitfield made the overtime unbearable.",
    ]
    result = analyze_exit_interview_text(responses)
    terms = {term for term, _n in result.top_terms}
    assert "alexandra" not in terms
    assert "whitfield" not in terms


# ── Term extraction ──────────────────────────────────────────────────────────

def test_top_terms_only_include_terms_meeting_min_document_frequency():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    for term, n in result.top_terms:
        assert n >= MIN_DOCUMENT_FREQUENCY


def test_term_extraction_method_is_reported():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    assert result.term_extraction_method in ("tfidf", "word_frequency")


# ── Narrative language discipline ───────────────────────────────────────────

def test_narrative_disclaims_causality():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    assert "not a causal driver" in result.narrative_en


def test_narrative_when_no_theme_reaches_threshold():
    responses = [
        "It was fine, nothing major to report about my time here at all.",
        "No strong feelings either way about the company honestly speaking.",
        "Just moving on to something different in my career path.",
        "Nothing specific comes to mind about my time working here.",
        "It was an okay experience overall, nothing stands out much.",
    ]
    result = analyze_exit_interview_text(responses)
    assert result.available is True
    assert result.theme_frequencies == []


# ── Serialization ────────────────────────────────────────────────────────────

def test_unavailable_result_serializes_cleanly():
    result = unavailable_exit_interview_result("test reason")
    d = exit_interview_intelligence_to_dict(result)
    assert d["available"] is False
    assert d["theme_frequencies"] == []
    assert d["top_terms"] == []


def test_to_dict_is_json_safe_and_complete():
    responses = _overtime_heavy_corpus(6)
    result = analyze_exit_interview_text(responses)
    d = exit_interview_intelligence_to_dict(result)
    assert isinstance(d["theme_frequencies"], list)
    assert isinstance(d["top_terms"], list)
    assert isinstance(d["sources"], list) and len(d["sources"]) == 2
