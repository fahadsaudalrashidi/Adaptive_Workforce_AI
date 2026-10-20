"""
Exit Interview / Free-Text Intelligence Engine — Phase 35.3.

Accepts free-text exit-interview or open-ended survey responses (an
additional, clearly OPTIONAL upload alongside the structured dataset — this
module never runs on the structured HR file itself) and extracts themes
using two complementary, fully offline techniques:

  1. A deterministic keyword/phrase classifier that maps each response to
     the SAME organizational-psychology constructs already used elsewhere
     in this platform (backend/core/employee_risk_scoring.py's
     _CONSTRUCT_MAP: JD-R, COR, Equity, Mobley, FFM theory anchors),
     labeled with the SAME evidence-strength taxonomy already defined in
     backend/core/theory_aware_column_mapper.py (DIRECT / STRONG_PROXY /
     WEAK_PROXY) rather than inventing a parallel one.
  2. TF-IDF term extraction (scikit-learn, already a platform dependency —
     guarded exactly like every other optional import in this codebase) to
     surface the most salient recurring terms across the whole response
     corpus, independent of the predefined theme dictionary. Falls back to
     plain word-frequency counting if scikit-learn is unavailable.

No LLM, no embedding model, no network call of any kind — consistent with
offline_mode_guard.py and this platform's explicit "classical/deterministic,
not generative" AI design (see PROJECT_FOR_CHATGPT.md's AI SYSTEM section).

PRIVACY / GOVERNANCE — this is the most sensitive data type this platform
accepts, so the rules are stricter than elsewhere:
  - Raw response text is NEVER returned in any API response, log, or export.
    Only (a) counts of how many responses matched a predefined theme, and
    (b) TF-IDF terms that appear in at least MIN_DOCUMENT_FREQUENCY
    *different* responses are ever surfaced — a one-off name or identifying
    detail typed by a single respondent cannot reach min_df=3 and is
    structurally excluded, not just policy-excluded.
  - Every response is regex-scrubbed for emails/phone numbers/national-ID-
    style patterns before any processing (matching employee_risk_scoring.py's
    _PII_COLUMN_PATTERNS discipline), even though scrubbed text is never
    returned — defense in depth.
  - Aggregation requires at least MIN_RESPONSES_FOR_AGGREGATE responses
    (5, matching config/settings.py's MIN_DEPT_GROUP_SIZE convention used
    for department-level small-sample suppression elsewhere) before any
    theme/term output is produced, to prevent a small response set from
    being effectively re-identifiable.
  - No causal language: a theme's frequency is reported as "mentioned in
    N responses," never as "causes attrition."

**Reused as a shared text-mining utility (Phase 34)**: the domain-agnostic
pieces of this module — `scrub_pii()`, `extract_top_terms_tfidf()` /
`extract_top_terms_word_frequency()`, `SKLEARN_AVAILABLE`, and the
`MIN_RESPONSES_FOR_AGGREGATE` / `MIN_DOCUMENT_FREQUENCY` thresholds — were
promoted from module-private (`_`-prefixed) to public names so that
`logistics_intelligence_engine.py` could import and call them directly for
its own returns-reason theme extraction, instead of re-implementing TF-IDF
term extraction a second time. `THEME_KEYWORDS` and `_classify_response()`
were deliberately NOT reused there — they encode HR attrition constructs
(JD-R, COR, Equity, Mobley, FFM) that have no semantic overlap with
logistics return reasons ("damaged in transit", "wrong item"), so Logistics
defines its own theme dictionary while sharing the underlying extraction
mechanism and privacy discipline.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# Phase 39: theory_aware_column_mapper.py (the theory/prediction system) was
# removed; these are just the 3 shared evidence-strength vocabulary labels
# this module always used for its own text-theme matching, not a computed
# construct or column mapping — inlined locally rather than pulled from a
# deleted module.
EVIDENCE_DIRECT       = "DIRECT"
EVIDENCE_STRONG_PROXY = "STRONG_PROXY"
EVIDENCE_WEAK_PROXY   = "WEAK_PROXY"

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

MIN_RESPONSES_FOR_AGGREGATE = 5
MIN_DOCUMENT_FREQUENCY = 3       # a term/theme must appear in >=3 distinct responses
MAX_TFIDF_TERMS = 15
MAX_RESPONSE_CHARS = 5_000       # guard against pathological single-response payloads

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_PATTERN = re.compile(r"\b(\+?\d[\d\s\-()]{7,}\d)\b")
_NATIONAL_ID_PATTERN = re.compile(r"\b\d{9,12}\b")

_ENGLISH_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "to", "of", "in", "on", "at", "for", "with", "about",
    "as", "by", "that", "this", "it", "i", "my", "me", "we", "our", "you",
    "your", "they", "their", "he", "she", "his", "her", "not", "no", "do",
    "did", "does", "have", "has", "had", "would", "could", "should", "will",
    "can", "just", "so", "very", "really", "get", "got", "than", "then",
})

# ── Theme dictionary — reuses employee_risk_scoring.py's construct taxonomy ──
# Each entry: construct_name -> (theory_anchor, direction, direct_phrases, proxy_phrases)
# direct_phrases  -> EVIDENCE_DIRECT match (specific, unambiguous exit-interview phrasing)
# proxy_phrases   -> EVIDENCE_STRONG_PROXY match (related but less specific wording)
# A single generic negative-sentiment cue with no phrase match at all is
# never elevated above EVIDENCE_WEAK_PROXY and is not theme-attributed.

THEME_KEYWORDS: dict[str, dict[str, Any]] = {
    "Overtime Demand": {
        "theory": "JD-R", "direction": "risk",
        "direct_phrases": ["too much overtime", "unpaid overtime", "excessive overtime", "mandatory overtime", "forced overtime"],
        "proxy_phrases": ["long hours", "overworked", "no time off", "working late", "working weekends"],
    },
    "Work-Life Balance": {
        "theory": "JD-R", "direction": "risk",
        "direct_phrases": ["no work life balance", "poor work-life balance", "no work-life balance"],
        "proxy_phrases": ["burnout", "burned out", "exhausted", "never home", "family time"],
    },
    "Compensation Equity": {
        "theory": "Equity", "direction": "risk",
        "direct_phrases": ["underpaid", "unfair pay", "pay is not fair", "salary is too low", "not paid fairly"],
        "proxy_phrases": ["low salary", "better offer", "higher pay elsewhere", "compensation"],
    },
    "Promotion Justice": {
        "theory": "Equity", "direction": "risk",
        "direct_phrases": ["passed over for promotion", "no promotion opportunities", "unfair promotion"],
        "proxy_phrases": ["no growth", "no career growth", "no advancement", "stuck in my role", "no path forward"],
    },
    "Supervisory Support": {
        "theory": "COR", "direction": "risk",
        "direct_phrases": ["bad manager", "poor management support", "manager did not support me", "unsupportive manager"],
        "proxy_phrases": ["lack of support", "no feedback", "management issues", "leadership problems"],
    },
    "Recognition Resource": {
        "theory": "COR", "direction": "risk",
        "direct_phrases": ["never recognized", "no recognition", "work goes unnoticed"],
        "proxy_phrases": ["undervalued", "unappreciated", "not valued"],
    },
    "Training/Career Resource": {
        "theory": "COR", "direction": "risk",
        "direct_phrases": ["no training provided", "lack of training", "no development opportunities"],
        "proxy_phrases": ["no upskilling", "no learning opportunities", "skills stagnant"],
    },
    "External Pull / Withdrawal": {
        "theory": "Mobley", "direction": "risk",
        "direct_phrases": ["received a better offer", "another company offered", "found a new job"],
        "proxy_phrases": ["better opportunity elsewhere", "career move", "new opportunity"],
    },
    "Job Stability Perception": {
        "theory": "Mobley", "direction": "risk",
        "direct_phrases": ["worried about layoffs", "job insecurity", "afraid of being laid off"],
        "proxy_phrases": ["uncertain future", "restructuring concerns", "instability"],
    },
    "Job Satisfaction": {
        "theory": "FFM", "direction": "protective",
        "direct_phrases": ["loved my job", "enjoyed working here", "great place to work"],
        "proxy_phrases": ["good experience", "positive environment", "happy here"],
    },
}

_ALL_THEMES = list(THEME_KEYWORDS.keys())


@dataclass(frozen=True)
class ThemeFrequency:
    construct: str
    theory_anchor: str
    direction: str            # "risk" | "protective"
    n_responses_mentioned: int
    pct_of_responses: float
    evidence_strength: str    # EVIDENCE_DIRECT | EVIDENCE_STRONG_PROXY (theme-level: best evidence found across matches)


@dataclass(frozen=True)
class ExitInterviewIntelligenceResult:
    available: bool
    reason: Optional[str]
    n_responses_total: int
    n_responses_analyzed: int
    theme_frequencies: list[ThemeFrequency]
    top_terms: list[tuple[str, int]]     # (term, n_distinct_responses) — never raw excerpts
    term_extraction_method: str          # "tfidf" | "word_frequency" | "unavailable"
    narrative_en: str
    narrative_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def scrub_pii(text: str) -> str:
    text = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = _NATIONAL_ID_PATTERN.sub("[REDACTED_ID]", text)
    text = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    return text


def unavailable_exit_interview_result(reason: str) -> ExitInterviewIntelligenceResult:
    """Public constructor for an `available=False` result."""
    return ExitInterviewIntelligenceResult(
        available=False,
        reason=reason,
        n_responses_total=0,
        n_responses_analyzed=0,
        theme_frequencies=[],
        top_terms=[],
        term_extraction_method="unavailable",
        narrative_en=reason,
        narrative_ar="بيانات نصوص مقابلات الخروج غير كافية أو غير متوفرة للتحليل.",
        governance_note=(
            "Exit-interview text analysis requires at least "
            f"{MIN_RESPONSES_FOR_AGGREGATE} responses before any aggregate "
            "output is produced, to prevent re-identification from a small "
            "sample. No individual response is ever returned or stored raw."
        ),
        sources=[],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def _classify_response(scrubbed_text: str) -> dict[str, str]:
    """Return {construct_name: evidence_strength} for every construct matched
    in this single response (best evidence level per construct)."""
    lowered = scrubbed_text.lower()
    matched: dict[str, str] = {}
    for construct, spec in THEME_KEYWORDS.items():
        if any(phrase in lowered for phrase in spec["direct_phrases"]):
            matched[construct] = EVIDENCE_DIRECT
        elif any(phrase in lowered for phrase in spec["proxy_phrases"]):
            matched[construct] = EVIDENCE_STRONG_PROXY
    return matched


def extract_top_terms_tfidf(documents: list[str]) -> list[tuple[str, int]]:
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=MIN_DOCUMENT_FREQUENCY,
        stop_words="english",
        max_features=200,
    )
    try:
        matrix = vectorizer.fit_transform(documents)
    except ValueError:
        # No terms survive min_df — corpus too small/sparse for TF-IDF.
        return extract_top_terms_word_frequency(documents)

    terms = vectorizer.get_feature_names_out()
    doc_frequency = (matrix > 0).sum(axis=0).A1  # number of documents containing each term
    scores = matrix.sum(axis=0).A1               # aggregate TF-IDF weight per term

    ranked = sorted(
        zip(terms, doc_frequency, scores),
        key=lambda x: x[2], reverse=True,
    )
    return [(str(term), int(df)) for term, df, _score in ranked[:MAX_TFIDF_TERMS]]


def extract_top_terms_word_frequency(documents: list[str]) -> list[tuple[str, int]]:
    """Deterministic fallback when scikit-learn is unavailable: count words
    that appear in at least MIN_DOCUMENT_FREQUENCY distinct responses."""
    doc_word_sets = []
    for doc in documents:
        words = re.findall(r"[a-zA-Z']+", doc.lower())
        doc_word_sets.append({w for w in words if len(w) > 2 and w not in _ENGLISH_STOPWORDS})

    doc_frequency: Counter = Counter()
    for word_set in doc_word_sets:
        doc_frequency.update(word_set)

    ranked = [(word, count) for word, count in doc_frequency.items() if count >= MIN_DOCUMENT_FREQUENCY]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:MAX_TFIDF_TERMS]


def analyze_exit_interview_text(
    responses: list[str],
) -> ExitInterviewIntelligenceResult:
    """
    Analyze a batch of free-text exit-interview / open-ended survey
    responses. Returns theme frequencies mapped to this platform's existing
    theory constructs, plus salient recurring terms, both purely aggregate.

    Parameters
    ----------
    responses : list of raw free-text strings, one per respondent. Empty/
               whitespace-only entries are dropped before the minimum-count
               check. Each response is truncated to MAX_RESPONSE_CHARS
               characters before processing (defensive limit only).
    """
    if not responses:
        return unavailable_exit_interview_result(
            "No exit-interview text was provided."
        )

    cleaned = [
        scrub_pii(str(r).strip()[:MAX_RESPONSE_CHARS])
        for r in responses
        if r is not None and str(r).strip()
    ]
    n_total = len(responses)
    n_analyzed = len(cleaned)

    if n_analyzed < MIN_RESPONSES_FOR_AGGREGATE:
        return unavailable_exit_interview_result(
            f"Only {n_analyzed} non-empty response(s) were provided. At least "
            f"{MIN_RESPONSES_FOR_AGGREGATE} are required before any aggregate "
            "theme analysis can be produced — this protects respondent "
            "anonymity in small samples."
        )

    # ── Theme classification ──────────────────────────────────────────────────
    construct_hits: dict[str, list[str]] = {c: [] for c in _ALL_THEMES}
    for text in cleaned:
        for construct, evidence in _classify_response(text).items():
            construct_hits[construct].append(evidence)

    theme_frequencies: list[ThemeFrequency] = []
    for construct, evidences in construct_hits.items():
        n_hits = len(evidences)
        if n_hits < MIN_DOCUMENT_FREQUENCY:
            continue  # suppress themes mentioned by too few respondents
        spec = THEME_KEYWORDS[construct]
        best_evidence = EVIDENCE_DIRECT if EVIDENCE_DIRECT in evidences else EVIDENCE_STRONG_PROXY
        theme_frequencies.append(ThemeFrequency(
            construct=construct,
            theory_anchor=spec["theory"],
            direction=spec["direction"],
            n_responses_mentioned=n_hits,
            pct_of_responses=round(100.0 * n_hits / n_analyzed, 1),
            evidence_strength=best_evidence,
        ))
    theme_frequencies.sort(key=lambda t: t.n_responses_mentioned, reverse=True)

    # ── Salient term extraction ───────────────────────────────────────────────
    if SKLEARN_AVAILABLE:
        top_terms = extract_top_terms_tfidf(cleaned)
        method = "tfidf"
    else:
        top_terms = extract_top_terms_word_frequency(cleaned)
        method = "word_frequency"

    # ── Narrative (non-causal, aggregate-only) ────────────────────────────────
    risk_themes = [t for t in theme_frequencies if t.direction == "risk"]
    if risk_themes:
        top = risk_themes[0]
        narrative_en = (
            f"Across {n_analyzed} exit-interview responses, the most frequently "
            f"mentioned risk-associated theme is '{top.construct}' "
            f"({top.n_responses_mentioned} responses, {top.pct_of_responses:.0f}%), "
            f"consistent with the {top.theory_anchor} framework already used "
            "elsewhere in this platform's risk scoring. This reflects what "
            "departing employees chose to mention, not a causal driver of "
            "attrition — themes should be corroborated with the structured "
            "risk analysis before acting on them."
        )
        narrative_ar = (
            f"عبر {n_analyzed} استجابة من مقابلات الخروج، الموضوع الأكثر "
            f"ذكراً المرتبط بالمخاطر هو '{top.construct}' "
            f"({top.n_responses_mentioned} استجابة، {top.pct_of_responses:.0f}%)."
        )
    else:
        narrative_en = (
            f"Across {n_analyzed} exit-interview responses, no single theme was "
            f"mentioned by at least {MIN_DOCUMENT_FREQUENCY} respondents using "
            "the recognised phrase set — responses may be too varied, too "
            "short, or not in English (theme matching is English-only in this "
            "version)."
        )
        narrative_ar = (
            f"عبر {n_analyzed} استجابة، لم يتم ذكر أي موضوع واحد من قبل "
            f"{MIN_DOCUMENT_FREQUENCY} مستجيبين على الأقل."
        )

    return ExitInterviewIntelligenceResult(
        available=True,
        reason=None,
        n_responses_total=n_total,
        n_responses_analyzed=n_analyzed,
        theme_frequencies=theme_frequencies,
        top_terms=top_terms,
        term_extraction_method=method,
        narrative_en=narrative_en,
        narrative_ar=narrative_ar,
        governance_note=(
            "Themes are derived from a predefined, auditable keyword set "
            "mapped to this platform's existing psychological constructs — "
            "not a generative model. No raw response text is returned, "
            "logged, or exported; only aggregate counts. Terms and themes "
            "mentioned by fewer than "
            f"{MIN_DOCUMENT_FREQUENCY} distinct respondents are suppressed. "
            "Not a substitute for qualified HR review of the underlying "
            "exit-interview process."
        ),
        sources=[
            "Theme taxonomy reuses backend/core/employee_risk_scoring.py's "
            "_CONSTRUCT_MAP (JD-R, COR, Equity, Mobley, FFM theory anchors).",
            "Evidence-strength labels reuse backend/core/theory_aware_column_mapper.py's "
            "DIRECT/STRONG_PROXY/WEAK_PROXY taxonomy.",
        ],
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


def exit_interview_intelligence_to_dict(r: ExitInterviewIntelligenceResult) -> dict[str, Any]:
    """Serialize ExitInterviewIntelligenceResult to a JSON-safe dict.
    Contains no raw response text under any circumstances."""
    return {
        "available": r.available,
        "reason": r.reason,
        "n_responses_total": r.n_responses_total,
        "n_responses_analyzed": r.n_responses_analyzed,
        "theme_frequencies": [
            {
                "construct": t.construct,
                "theory_anchor": t.theory_anchor,
                "direction": t.direction,
                "n_responses_mentioned": t.n_responses_mentioned,
                "pct_of_responses": t.pct_of_responses,
                "evidence_strength": t.evidence_strength,
            }
            for t in r.theme_frequencies
        ],
        "top_terms": [{"term": term, "n_responses": n} for term, n in r.top_terms],
        "term_extraction_method": r.term_extraction_method,
        "narrative_en": r.narrative_en,
        "narrative_ar": r.narrative_ar,
        "governance_note": r.governance_note,
        "sources": r.sources,
        "computed_at": r.computed_at,
    }
