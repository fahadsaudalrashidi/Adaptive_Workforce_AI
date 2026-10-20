# -*- coding: utf-8 -*-
"""
Enterprise Language Guard
==========================

Audits all AI-generated text output for governance-unsafe language.

Enforces:
  - Probabilistic framing (never deterministic outcome claims)
  - No causal language for workforce decisions
  - No medical-style risk language
  - No legal-risk phrasing
  - No Saudi-specific cultural sensitivity violations
  - No unsupported certainty claims about individual employees
  - No GDPR/PDPL-violating identification language
  - Governance-safe alternative vocabulary

Design:
  - Input: any string (report text, insight, executive summary)
  - Output: LanguageAuditReport with violations + safe alternatives
  - Does NOT modify text silently — returns violations and suggestions
  - Caller decides whether to replace or reject

Does NOT:
  - Train models
  - Modify DataFrames
  - Override upstream governance decisions
  - Filter user input (only AI-generated output)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# VIOLATION CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────

CAT_DETERMINISTIC_CLAIM    = "DETERMINISTIC_CLAIM"
CAT_CAUSAL_LANGUAGE        = "CAUSAL_LANGUAGE"
CAT_MEDICAL_LANGUAGE       = "MEDICAL_LANGUAGE"
CAT_LEGAL_RISK             = "LEGAL_RISK"
CAT_INDIVIDUAL_TARGETING   = "INDIVIDUAL_TARGETING"
CAT_CULTURAL_SENSITIVITY   = "CULTURAL_SENSITIVITY"
CAT_UNSUPPORTED_CERTAINTY  = "UNSUPPORTED_CERTAINTY"
CAT_PII_EXPOSURE           = "PII_LANGUAGE"


# ─────────────────────────────────────────────────────────────────────────────
# VIOLATION RULE LIBRARY
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LanguageRule:
    pattern: str                # regex or exact phrase (case-insensitive)
    category: str
    severity: str               # CRITICAL / HIGH / MEDIUM
    reason: str
    safe_alternative: str
    is_regex: bool = False


_RULES: List[LanguageRule] = [

    # ── Deterministic outcome claims ──────────────────────────────────────────
    LanguageRule(
        pattern=r"will (resign|leave|quit|attrit|separate|exit|terminate)",
        category=CAT_DETERMINISTIC_CLAIM, severity="CRITICAL",
        reason="Deterministic resignation claim — model outputs are probabilistic, not certain.",
        safe_alternative="shows elevated predicted risk of voluntary separation",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"(is going to|going to) (leave|resign|quit|separate)",
        category=CAT_DETERMINISTIC_CLAIM, severity="CRITICAL",
        reason="Future-tense deterministic claim — prohibited.",
        safe_alternative="has been flagged for structured retention review",
        is_regex=True,
    ),
    LanguageRule(
        pattern="certain to leave",
        category=CAT_DETERMINISTIC_CLAIM, severity="CRITICAL",
        reason="Absolute certainty claim is scientifically unsupported.",
        safe_alternative="shows the highest predicted risk in this review period",
    ),
    LanguageRule(
        pattern="guaranteed to leave",
        category=CAT_DETERMINISTIC_CLAIM, severity="CRITICAL",
        reason="Guarantee of resignation — scientifically and legally indefensible.",
        safe_alternative="is in the highest-risk segment — requires human review",
    ),
    LanguageRule(
        pattern="predicted to resign",
        category=CAT_DETERMINISTIC_CLAIM, severity="HIGH",
        reason="Resignation prediction stated as fact, not probability.",
        safe_alternative="has a predicted probability of voluntary separation above the review threshold",
    ),
    LanguageRule(
        pattern=r"(100%|100 percent) (chance|probability|likely)",
        category=CAT_DETERMINISTIC_CLAIM, severity="CRITICAL",
        reason="100% probability claim is scientifically impossible for HR outcomes.",
        safe_alternative="is in the critical risk tier — requires immediate HR review",
        is_regex=True,
    ),

    # ── Causal language ───────────────────────────────────────────────────────
    LanguageRule(
        pattern=r"(causes?|causing|caused) (attrition|resignation|turnover|departure)",
        category=CAT_CAUSAL_LANGUAGE, severity="HIGH",
        reason="Causal claim not supported by observational HR data.",
        safe_alternative="is associated with elevated predicted risk",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"(leads? to|lead to|leading to) (resignation|attrition|turnover)",
        category=CAT_CAUSAL_LANGUAGE, severity="HIGH",
        reason="Causal directionality cannot be established from cross-sectional data.",
        safe_alternative="is associated with elevated attrition risk patterns",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"(directly|proven|definitively) (causes?|affects?|drives?)",
        category=CAT_CAUSAL_LANGUAGE, severity="HIGH",
        reason="Causal language with certainty modifier — not supported by ML output.",
        safe_alternative="is correlated with",
        is_regex=True,
    ),
    LanguageRule(
        pattern="the reason for",
        category=CAT_CAUSAL_LANGUAGE, severity="MEDIUM",
        reason="Assigning a single causal reason for complex HR behavior is inappropriate.",
        safe_alternative="a factor associated with",
    ),

    # ── Medical/clinical language ─────────────────────────────────────────────
    LanguageRule(
        pattern=r"(diagnos|disorder|syndrome|patholog|symptom|clinical|medical)",
        category=CAT_MEDICAL_LANGUAGE, severity="HIGH",
        reason="Medical/clinical language is inappropriate for organizational risk assessment.",
        safe_alternative="organizational risk indicator",
        is_regex=True,
    ),
    LanguageRule(
        pattern="burnout diagnosis",
        category=CAT_MEDICAL_LANGUAGE, severity="CRITICAL",
        reason="Burnout diagnosis requires clinical assessment — ML output is a risk score only.",
        safe_alternative="BurnoutRisk score above the organizational review threshold",
    ),
    LanguageRule(
        pattern="mental health",
        category=CAT_MEDICAL_LANGUAGE, severity="HIGH",
        reason="Mental health language in HR context creates legal liability.",
        safe_alternative="employee wellbeing indicator",
    ),
    LanguageRule(
        pattern="psychological disorder",
        category=CAT_MEDICAL_LANGUAGE, severity="CRITICAL",
        reason="Clinical psychiatric language — never appropriate in HR ML output.",
        safe_alternative="organizational stress indicator",
    ),

    # ── Legal-risk phrasing ───────────────────────────────────────────────────
    LanguageRule(
        pattern=r"\b(terminate|terminated|termination)\b",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Termination language creates employment law liability.",
        safe_alternative="employment transition",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(fire|fires|fired)\b",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Dismissal language in AI output is a legal risk.",
        safe_alternative="exit from organization",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(dismiss|dismissed|dismissal)\b",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Dismissal language — prohibited in AI-generated HR reports.",
        safe_alternative="employment separation",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(redundant|redundancy|laid off|layoff)\b",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Redundancy/layoff language creates legal and reputational risk.",
        safe_alternative="workforce restructuring review",
        is_regex=True,
    ),
    LanguageRule(
        pattern="must be removed",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Directive language for employee removal — creates legal exposure.",
        safe_alternative="recommended for structured HR review",
    ),
    LanguageRule(
        pattern="should be removed",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Directive removal recommendation — prohibited in AI output.",
        safe_alternative="flagged for human review",
    ),
    LanguageRule(
        pattern="eliminate this employee",
        category=CAT_LEGAL_RISK, severity="CRITICAL",
        reason="Directive language for employee elimination — never appropriate.",
        safe_alternative="conduct structured review for this employee",
    ),

    # ── Individual targeting ──────────────────────────────────────────────────
    LanguageRule(
        pattern=r"employee #?\d+",
        category=CAT_INDIVIDUAL_TARGETING, severity="HIGH",
        reason="Direct individual employee identification in reports.",
        safe_alternative="employee in priority review segment",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"(employee|person|individual) (named|called|identified as)",
        category=CAT_INDIVIDUAL_TARGETING, severity="CRITICAL",
        reason="Named individual targeting in AI report is a PDPL/GDPR violation.",
        safe_alternative="employee in the flagged segment",
        is_regex=True,
    ),
    LanguageRule(
        pattern="this specific employee",
        category=CAT_INDIVIDUAL_TARGETING, severity="HIGH",
        reason="Individual identification in AI output.",
        safe_alternative="employee in the priority review tier",
    ),

    # ── Cultural sensitivity (Saudi context) ──────────────────────────────────
    LanguageRule(
        pattern=r"\b(saudi|non.saudi|expat|expatriate)\b.*\b(risk|attrition|resign|leave)\b",
        category=CAT_CULTURAL_SENSITIVITY, severity="HIGH",
        reason="Nationality-based risk attribution creates discrimination liability under Saudi law.",
        safe_alternative="employees in the flagged risk segment",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(gender|female|male|woman|man)\b.*\b(risk|attrition|resign)\b",
        category=CAT_CULTURAL_SENSITIVITY, severity="HIGH",
        reason="Gender-based attrition prediction creates discrimination liability.",
        safe_alternative="employees in the priority review segment",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(nitaqat|saudization|saudisation)\b.*\b(risk|attrition|low.performance)\b",
        category=CAT_CULTURAL_SENSITIVITY, severity="HIGH",
        reason="Linking Saudization categories to attrition risk creates legal exposure.",
        safe_alternative="organizational workforce composition indicator",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"\b(religion|religious|islamic|muslim)\b",
        category=CAT_CULTURAL_SENSITIVITY, severity="HIGH",
        reason="Religious attribute reference in HR risk assessment violates protected characteristics.",
        safe_alternative=(
            "[remove religious reference — use organizational or behavioral indicators only]"
        ),
        is_regex=True,
    ),

    # ── Unsupported certainty ─────────────────────────────────────────────────
    LanguageRule(
        pattern=r"(definitely|certainly|undoubtedly|without doubt|unquestionably) (will|is|has)",
        category=CAT_UNSUPPORTED_CERTAINTY, severity="HIGH",
        reason="Certainty modifier with definitive claim — not supported by probabilistic model.",
        safe_alternative="is associated with a high predicted probability of",
        is_regex=True,
    ),
    LanguageRule(
        pattern="proven to reduce attrition",
        category=CAT_UNSUPPORTED_CERTAINTY, severity="HIGH",
        reason="Causal intervention claim not supported by observational ML.",
        safe_alternative="associated with lower predicted risk in the training data",
    ),
    LanguageRule(
        pattern="guaranteed to improve",
        category=CAT_UNSUPPORTED_CERTAINTY, severity="HIGH",
        reason="Outcome guarantee from HR ML is scientifically unsupported.",
        safe_alternative="associated with lower predicted risk",
    ),

    # ── PII exposure language ─────────────────────────────────────────────────
    LanguageRule(
        pattern=r"national id:?\s*\d+",
        category=CAT_PII_EXPOSURE, severity="CRITICAL",
        reason="National ID number in AI output — PDPL violation.",
        safe_alternative="[REDACTED — employee ID]",
        is_regex=True,
    ),
    LanguageRule(
        pattern=r"iqama:?\s*\d+",
        category=CAT_PII_EXPOSURE, severity="CRITICAL",
        reason="Iqama number in AI output — PDPL violation.",
        safe_alternative="[REDACTED — residency ID]",
        is_regex=True,
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LanguageViolation:
    """A single language governance violation."""
    matched_text: str
    category: str
    severity: str
    reason: str
    safe_alternative: str
    position: int           # character position in original text


@dataclass
class LanguageAuditReport:
    """Full language audit result for one text string."""
    is_compliant: bool
    n_critical: int
    n_high: int
    n_medium: int
    violations: List[LanguageViolation]
    safe_text: Optional[str]    # best-effort replacement text (may be None)
    summary: str
    governance_notes: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# GUARD
# ─────────────────────────────────────────────────────────────────────────────

class EnterpriseLanguageGuard:
    """
    Audits AI-generated text for governance-unsafe language.

    Usage
    -----
    guard = EnterpriseLanguageGuard()
    report = guard.audit("This employee will resign next quarter.")
    if not report.is_compliant:
        logger.warning("Language violation: %s", report.summary)
    """

    def audit(self, text: str) -> LanguageAuditReport:
        """
        Audit a text string for language governance violations.

        Parameters
        ----------
        text : The AI-generated text to audit.

        Returns
        -------
        LanguageAuditReport with all violations found and safe alternatives.
        """
        if not text or not text.strip():
            return LanguageAuditReport(
                is_compliant=True, n_critical=0, n_high=0, n_medium=0,
                violations=[], safe_text=text, summary="No text to audit.",
            )

        violations: List[LanguageViolation] = []
        text_lower = text.lower()

        for rule in _RULES:
            if rule.is_regex:
                for m in re.finditer(rule.pattern, text_lower, re.IGNORECASE):
                    violations.append(LanguageViolation(
                        matched_text=text[m.start():m.end()],
                        category=rule.category,
                        severity=rule.severity,
                        reason=rule.reason,
                        safe_alternative=rule.safe_alternative,
                        position=m.start(),
                    ))
            else:
                idx = text_lower.find(rule.pattern.lower())
                if idx != -1:
                    end = idx + len(rule.pattern)
                    violations.append(LanguageViolation(
                        matched_text=text[idx:end],
                        category=rule.category,
                        severity=rule.severity,
                        reason=rule.reason,
                        safe_alternative=rule.safe_alternative,
                        position=idx,
                    ))

        # Deduplicate by position (take highest severity per position)
        violations = _deduplicate_violations(violations)

        n_crit   = sum(1 for v in violations if v.severity == "CRITICAL")
        n_high   = sum(1 for v in violations if v.severity == "HIGH")
        n_medium = sum(1 for v in violations if v.severity == "MEDIUM")

        is_compliant = (n_crit == 0 and n_high == 0)

        # Best-effort safe text generation
        safe_text = self._apply_safe_replacements(text, violations) if violations else text

        gov_notes: List[str] = []
        if n_crit > 0:
            gov_notes.append(
                f"{n_crit} CRITICAL language violations detected. "
                "Text must not be shown to users without correction."
            )
        if any(v.category == CAT_LEGAL_RISK for v in violations):
            gov_notes.append(
                "LEGAL RISK: Text contains language that creates employment law liability. "
                "Legal review required before publication."
            )
        if any(v.category == CAT_CULTURAL_SENSITIVITY for v in violations):
            gov_notes.append(
                "CULTURAL SENSITIVITY: Text references protected characteristics "
                "(nationality, gender, religion). Review by Saudi HR specialist required."
            )
        if any(v.category == CAT_PII_EXPOSURE for v in violations):
            gov_notes.append(
                "PII DETECTED: Text contains personally identifiable information. "
                "PDPL requires immediate redaction before any sharing."
            )

        if not violations:
            summary = "Language audit: COMPLIANT. No violations detected."
        else:
            cats = list(dict.fromkeys(v.category for v in violations))
            summary = (
                f"Language audit: {'COMPLIANT' if is_compliant else 'NON-COMPLIANT'}. "
                f"{len(violations)} violation(s): {n_crit} CRITICAL, {n_high} HIGH, "
                f"{n_medium} MEDIUM. Categories: {cats}."
            )

        logger.debug("EnterpriseLanguageGuard: %s", summary)

        return LanguageAuditReport(
            is_compliant=is_compliant,
            n_critical=n_crit,
            n_high=n_high,
            n_medium=n_medium,
            violations=violations,
            safe_text=safe_text,
            summary=summary,
            governance_notes=gov_notes,
        )

    def audit_batch(self, texts: List[str]) -> List[LanguageAuditReport]:
        """Audit multiple text strings, one report per string."""
        return [self.audit(t) for t in texts]

    def is_compliant(self, text: str) -> bool:
        """Quick boolean compliance check."""
        return self.audit(text).is_compliant

    def get_safe_text(self, text: str) -> str:
        """Return best-effort safe replacement text."""
        report = self.audit(text)
        return report.safe_text or text

    def _apply_safe_replacements(
        self,
        text: str,
        violations: List[LanguageViolation],
    ) -> str:
        """Apply safe alternative substitutions to the text."""
        result = text
        # Sort by position descending so replacements don't shift indices
        for v in sorted(violations, key=lambda x: x.position, reverse=True):
            # Only replace non-empty, non-redaction alternatives
            if v.safe_alternative and not v.safe_alternative.startswith("["):
                try:
                    result = (
                        result[:v.position]
                        + v.safe_alternative
                        + result[v.position + len(v.matched_text):]
                    )
                except Exception:
                    pass
        return result


# ─────────────────────────────────────────────────────────────────────────────
# SAFE LANGUAGE VOCABULARY
# ─────────────────────────────────────────────────────────────────────────────

SAFE_ATTRITION_VOCABULARY: Dict[str, str] = {
    "will leave":               "shows elevated predicted risk of voluntary separation",
    "will resign":              "is in the priority retention review segment",
    "will quit":                "shows elevated predicted attrition risk",
    "employees will attrit":    "employees with elevated predicted separation risk",
    "certain to leave":         "in the highest predicted risk tier",
    "high-risk employees":      "employees in the priority review segment",
    "critical employees":       "employees with the highest predicted risk scores",
    "require immediate action": "flagged for structured HR review",
    "must intervene":           "recommended for human validation",
    "increases attrition":      "is associated with elevated predicted attrition risk",
    "decreases attrition":      "is associated with lower predicted attrition risk",
    "terminate":                "employment transition",
    "terminated":               "separated from employment",
    "fire":                     "exit from organization",
    "dismiss":                  "separate from",
    "burnout":                  "organizational stress indicator above review threshold",
    "mental health":            "employee wellbeing indicator",
}


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _deduplicate_violations(
    violations: List[LanguageViolation],
) -> List[LanguageViolation]:
    """Remove overlapping violations, keeping the highest-severity match per position."""
    if not violations:
        return []

    severity_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "INFO": 0}
    seen: Dict[int, LanguageViolation] = {}
    for v in violations:
        pos = v.position
        if pos not in seen or severity_rank.get(v.severity, 0) > severity_rank.get(seen[pos].severity, 0):
            seen[pos] = v

    return sorted(seen.values(), key=lambda x: x.position)


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def audit_language(text: str) -> LanguageAuditReport:
    """One-call convenience wrapper around EnterpriseLanguageGuard.audit()."""
    return EnterpriseLanguageGuard().audit(text)


def is_language_compliant(text: str) -> bool:
    """True if text passes language governance with no CRITICAL or HIGH violations."""
    return EnterpriseLanguageGuard().is_compliant(text)
