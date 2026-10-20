"""
Zakat Base Estimator — Phase 37.

**Investigation-first, per the brief's own explicit instruction — read this
before touching the code below.** Every other module built this session
(including the two siblings in this same phase, GOSI and Payroll Budget)
operates on employee-level HR data: one row per person, columns like
salary/department/nationality. Zakat, per ZATCA's actual 2024 Executive
Regulations for Zakat Collection ("the Bylaws"), is computed from
COMPANY-LEVEL BALANCE-SHEET data — equity, provisions, fixed assets,
liabilities — a fundamentally different data shape this platform has never
ingested. Building this as an employee-upload feature would be a category
error; the brief itself anticipated this and asked for a manual-entry form
instead. That part of the design was clear before research even started.

**What research changed: whether to ship a liability figure at all.**
Live search (see PHASE_25_GOSI_BUDGET_ZAKAT_REPORT.md for full sources)
found the REAL ZATCA Bylaws methodology is materially more complex than
the brief's own draft formula ("equity + net income adjustments +
long-term liabilities/provisions − net fixed assets and certain
deductions"). Specifically:

- The real Zakat base starts from a DIFFERENCE between book net profit and
  adjusted net profit (not simply "net income"), then adds equity/equity-
  like items and QUALIFYING non-current liabilities, then subtracts a list
  of over a DOZEN specifically-defined deductible asset categories
  (qualifying investments, non-available-for-sale raw materials, net fixed
  assets, non-trading intangibles, employee housing assets, statutory
  deposits, deferred tax assets, qualifying sukuk/bonds, investment
  properties not held for sale, assets under concession arrangements,
  capital projects under construction not for sale, right-of-use assets,
  qualifying overdue government receivables) — each with its own
  eligibility test this module cannot verify from four numbers.
- There is a MINIMUM/MAXIMUM base comparison: if adjusted net profit
  exceeds book net profit, the base uses net assets plus the difference;
  otherwise it uses the adjusted net profit figure directly — a branch a
  short form cannot represent.
- Liabilities are netted CATEGORY-BY-CATEGORY against specific asset
  classes (current liabilities against deductible current assets,
  non-current liabilities against non-deductible non-current assets), not
  simply summed and subtracted.

**Decision: scope down to an explicitly-labeled SIMPLIFIED TRADITIONAL
formula, not the real ZATCA Bylaws methodology — ship it, but never call
it compliant.** The brief's own fallback options were "scope down further
(e.g. just the base calculation with heavy caveats, no liability figure)"
or "stop and report the finding instead of shipping something misleading."
A simpler traditional approximation — Zakat Base ≈ Equity + Long-term
liabilities/provisions − Net fixed assets − Other qualifying deductions —
IS independently, repeatedly cited across multiple sources found this
phase as a widely-used STARTING-POINT approximation distinct from the full
Bylaws netting methodology, in the same spirit as this platform's existing
"illustrative, not authoritative" modules (Nitaqat's Saudization estimate,
Overtime Cost Intelligence). The 2.5% rate itself is NOT in dispute across
any source found — it is applied here. What makes this responsible rather
than misleading is that the gap to the real methodology is disclosed
EXPLICITLY AND SPECIFICALLY (the actual deductible-category list above,
not a generic "consult a professional" boilerplate) in every result and on
the page itself, and the module NEVER claims to be ZATCA-compliant or
filing-ready anywhere in its output. This is a genuinely different
judgment call from the disciplinary-letter exclusion in the HR Letter
Generator phase (where NO simplified version is safe because the harm
lands on a specific named individual with no mitigating context) — here, a
clearly-labeled directional planning number carries far lower risk than a
fabricated disciplinary accusation, provided the labeling is honest and
specific, which this module enforces structurally (see
`ZAKAT_DISCLAIMER_EN`/`_AR` and `METHODOLOGY_GAP_NOTE_EN`/`_AR` below,
rendered on every result, not just documented here).

**Strict non-approximation, same discipline as every numeric module this
session.** `total_equity`, `long_term_liabilities_provisions`, and
`net_fixed_assets` are REQUIRED — if any is missing, this module reports
exactly which field is missing rather than defaulting it to zero (a zero
default would silently understate/overstate a real base). `other_deductions`
defaults to 0.0 ONLY because "I have no additional deductions to declare"
is a legitimate, meaningful user assertion (unlike a missing salary or
missing equity figure, which have no meaningful default).

No dataframe/file upload is involved anywhere in this module — a manual
numeric-entry form is the entire interaction surface, by design (see
above).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

ZAKAT_RATE = 0.025  # 2.5% — the one figure with no source disagreement found this phase.

ZAKAT_SOURCES = [
    "Saudi Arabia issues new Executive Regulations for Zakat Collection — EY Global "
    "(https://www.ey.com/en_gl/technical/tax-alerts/saudi-arabia-issues-new-executive-regulations-for-zakat-collecti): "
    "the real Zakat base starts from book-vs-adjusted net profit, adds equity/equity-like "
    "items and qualifying non-current liabilities, then deducts specifically-defined "
    "allowable assets — confirms this is a netting methodology, not a simple sum.",
    "Mezan — Zakat Base: What it is and How to Calculate It "
    "(https://mezan.sa/articles/zakat-base): confirms the 2.5% rate and the general "
    "equity/liabilities-minus-fixed-assets shape of the traditional simplified formula "
    "this module actually implements.",
    "How to Calculate Zakat: New Minimum & Maximum Zakat Base — Gridlines "
    "(https://www.gridlines.com/blog/how-to-calculate-zakat/): confirms the minimum/"
    "maximum base comparison (net assets + profit-adjustment-difference vs. adjusted net "
    "profit alone) this module deliberately does NOT attempt to replicate.",
    "Implementing Regulations For Zakat Collection 1445H (2024) — ZATCA official Bylaws "
    "(https://zatca.gov.sa/en/RulesRegulations/Documents/ZAKAT%20COLLECTION.pdf): lists "
    "12+ specifically-defined deductible asset categories (qualifying investments, "
    "non-trading intangibles, employee housing assets, statutory deposits, deferred tax "
    "assets, qualifying sukuk/bonds, right-of-use assets, etc.) and deductible-liability "
    "categories (short-term debts due within the fiscal year, accrued operating expenses) "
    "— confirms the real methodology is materially more granular than this module's "
    "simplified formula.",
    "A Comprehensive Guide to Zakat Calculation for Companies in Saudi Arabia — Ethraa "
    "Al-Sharq (https://ethraa-alsharq.com/en/zakat-calculation/): corroborates the "
    "traditional simplified equity + long-term liabilities - fixed assets approach as a "
    "commonly-cited planning starting point, distinct from full ZATCA compliance "
    "preparation.",
]

METHODOLOGY_GAP_NOTE_EN = (
    "This is a SIMPLIFIED TRADITIONAL approximation (Equity + Long-Term Liabilities/"
    "Provisions − Net Fixed Assets − Other Deductions), NOT the actual ZATCA 2024 Bylaws "
    "methodology. The real methodology nets specific categories of current/non-current "
    "assets against liabilities, applies a minimum/maximum base comparison based on "
    "book-vs-adjusted net profit, and recognizes over a dozen individually-defined "
    "deductible asset categories (e.g. qualifying investments, employee housing assets, "
    "statutory deposits, deferred tax assets, right-of-use assets) this simplified form "
    "does not collect. This tool CANNOT be used to prepare an actual ZATCA filing."
)
METHODOLOGY_GAP_NOTE_AR = (
    "هذا تقدير مبسّط تقليدي (حقوق الملكية + الالتزامات طويلة الأجل/المخصصات − صافي "
    "الأصول الثابتة − خصومات أخرى)، وليس منهجية لوائح هيئة الزكاة والضريبة والجمارك "
    "(زاتكا) الفعلية لعام 2024. تُقاصّ المنهجية الحقيقية فئات محددة من الأصول المتداولة "
    "وغير المتداولة مقابل الالتزامات، وتطبّق مقارنة بين الحد الأدنى والأقصى للوعاء "
    "استناداً إلى صافي الربح الدفتري مقابل المعدَّل، وتعترف بأكثر من اثنتي عشرة فئة أصول "
    "قابلة للخصم مُعرَّفة فردياً (مثل الاستثمارات المؤهلة، وأصول سكن الموظفين، والودائع "
    "النظامية، وأصول الضريبة المؤجلة، وأصول حق الاستخدام) لا تجمعها هذه الأداة المبسّطة. "
    "لا يمكن استخدام هذه الأداة لإعداد إقرار زكوي فعلي."
)
ZAKAT_DISCLAIMER_EN = (
    "This is a simplified planning ESTIMATE only — it is NOT a ZATCA filing, NOT a "
    "substitute for qualified tax/zakat professional preparation, and NOT compliant with "
    "the actual ZATCA 2024 Executive Regulations methodology (see the methodology gap note "
    "above). Actual zakat filings require full financial statement detail categorized per "
    "those Regulations. Do not use this figure for any regulatory filing, tax provision, or "
    "board-level financial commitment without qualified professional review."
)
ZAKAT_DISCLAIMER_AR = (
    "هذا تقدير تخطيطي مبسّط فقط — وليس إقراراً زكوياً لدى هيئة الزكاة والضريبة والجمارك "
    "(زاتكا)، وليس بديلاً عن الإعداد المتخصص من محاسب زكاة/ضرائب مؤهل، وليس متوافقاً مع "
    "منهجية اللوائح التنفيذية الفعلية لعام 2024 (انظر ملاحظة الفجوة المنهجية أعلاه). "
    "تتطلب الإقرارات الزكوية الفعلية تفاصيل كاملة للقوائم المالية مصنّفة وفق تلك اللوائح. "
    "لا تستخدم هذا الرقم في أي إقرار نظامي أو مخصص ضريبي أو التزام مالي على مستوى مجلس "
    "الإدارة دون مراجعة متخصصة مؤهلة."
)


@dataclass(frozen=True)
class ZakatInputs:
    total_equity_sar: Optional[float]
    long_term_liabilities_provisions_sar: Optional[float]
    net_fixed_assets_sar: Optional[float]
    other_deductions_sar: Optional[float] = 0.0


@dataclass(frozen=True)
class ZakatEstimateResult:
    available: bool
    reason: Optional[str]
    missing_fields: list[str]
    total_equity_sar: Optional[float]
    long_term_liabilities_provisions_sar: Optional[float]
    net_fixed_assets_sar: Optional[float]
    other_deductions_sar: Optional[float]
    zakat_base_sar: Optional[float]
    zakat_rate: float
    estimated_zakat_liability_sar: Optional[float]
    methodology_gap_note_en: str
    methodology_gap_note_ar: str
    disclaimer_en: str
    disclaimer_ar: str
    sources: list[str]
    computed_at: str


_REQUIRED_FIELD_LABELS_EN = {
    "total_equity_sar": "Total Equity",
    "long_term_liabilities_provisions_sar": "Long-Term Liabilities / Provisions",
    "net_fixed_assets_sar": "Net Fixed Assets",
}
_REQUIRED_FIELD_LABELS_AR = {
    "total_equity_sar": "إجمالي حقوق الملكية",
    "long_term_liabilities_provisions_sar": "الالتزامات طويلة الأجل / المخصصات",
    "net_fixed_assets_sar": "صافي الأصول الثابتة",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_zakat_base(inputs: ZakatInputs) -> ZakatEstimateResult:
    """Never raises. Strict non-approximation: any missing required field
    means available=False with the exact missing field(s) named — never a
    zero-defaulted or otherwise guessed value for a real tax-adjacent
    figure. See module docstring for the full methodology-gap disclosure
    this function's result always carries."""
    missing: list[str] = []
    if inputs.total_equity_sar is None:
        missing.append("total_equity_sar")
    if inputs.long_term_liabilities_provisions_sar is None:
        missing.append("long_term_liabilities_provisions_sar")
    if inputs.net_fixed_assets_sar is None:
        missing.append("net_fixed_assets_sar")

    if missing:
        missing_labels_en = ", ".join(_REQUIRED_FIELD_LABELS_EN[m] for m in missing)
        return ZakatEstimateResult(
            available=False,
            reason=(
                f"Cannot compute a Zakat base estimate — missing required field(s): "
                f"{missing_labels_en}. This module never estimates a missing balance-sheet "
                "figure for a real tax-adjacent calculation."
            ),
            missing_fields=missing,
            total_equity_sar=inputs.total_equity_sar,
            long_term_liabilities_provisions_sar=inputs.long_term_liabilities_provisions_sar,
            net_fixed_assets_sar=inputs.net_fixed_assets_sar,
            other_deductions_sar=inputs.other_deductions_sar,
            zakat_base_sar=None, zakat_rate=ZAKAT_RATE, estimated_zakat_liability_sar=None,
            methodology_gap_note_en=METHODOLOGY_GAP_NOTE_EN, methodology_gap_note_ar=METHODOLOGY_GAP_NOTE_AR,
            disclaimer_en=ZAKAT_DISCLAIMER_EN, disclaimer_ar=ZAKAT_DISCLAIMER_AR,
            sources=ZAKAT_SOURCES, computed_at=_now(),
        )

    other_deductions = inputs.other_deductions_sar if inputs.other_deductions_sar is not None else 0.0
    raw_base = (
        inputs.total_equity_sar
        + inputs.long_term_liabilities_provisions_sar
        - inputs.net_fixed_assets_sar
        - other_deductions
    )
    zakat_base = round(max(0.0, raw_base), 2)
    liability = round(zakat_base * ZAKAT_RATE, 2)

    return ZakatEstimateResult(
        available=True, reason=None, missing_fields=[],
        total_equity_sar=inputs.total_equity_sar,
        long_term_liabilities_provisions_sar=inputs.long_term_liabilities_provisions_sar,
        net_fixed_assets_sar=inputs.net_fixed_assets_sar,
        other_deductions_sar=other_deductions,
        zakat_base_sar=zakat_base, zakat_rate=ZAKAT_RATE, estimated_zakat_liability_sar=liability,
        methodology_gap_note_en=METHODOLOGY_GAP_NOTE_EN, methodology_gap_note_ar=METHODOLOGY_GAP_NOTE_AR,
        disclaimer_en=ZAKAT_DISCLAIMER_EN, disclaimer_ar=ZAKAT_DISCLAIMER_AR,
        sources=ZAKAT_SOURCES, computed_at=_now(),
    )


def zakat_estimate_to_dict(r: ZakatEstimateResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "missing_fields": r.missing_fields,
        "total_equity_sar": r.total_equity_sar,
        "long_term_liabilities_provisions_sar": r.long_term_liabilities_provisions_sar,
        "net_fixed_assets_sar": r.net_fixed_assets_sar,
        "other_deductions_sar": r.other_deductions_sar,
        "zakat_base_sar": r.zakat_base_sar, "zakat_rate": r.zakat_rate,
        "estimated_zakat_liability_sar": r.estimated_zakat_liability_sar,
        "methodology_gap_note_en": r.methodology_gap_note_en,
        "methodology_gap_note_ar": r.methodology_gap_note_ar,
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "sources": r.sources, "computed_at": r.computed_at,
    }
