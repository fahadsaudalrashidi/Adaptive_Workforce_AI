"""Phase 32.95 — Proof generation script. Generates PPTX + HTML and verifies both."""
import sys, os, io, json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

REALISTIC_DATA = {
    "totalEmployeeRecords": 847,
    "filename": "STC_Workforce_Q2_2026.csv",
    "scoredAt": "2026-06-02T10:00:00",
    "datasetHash": "sha256:abc123",
    "averageRiskScore": 41.3,
    "averageStabilityScore": 62.4,
    "governanceStatus": "active",
    "scoringWarnings": [],
    "matchedConstructCount": 12,
    "riskBandCounts": {
        "Priority Review": 94,
        "Strategic Concern": 127,
        "Monitoring": 203,
        "Stable": 423,
    },
    "executiveSummary": (
        "Analysis of 847 employees reveals that 221 individuals (26.1%) are classified "
        "in elevated risk stability bands. The highest-risk departments are Engineering, "
        "Operations, and Customer Experience. Financial exposure is estimated at SAR 26.5M "
        "under conservative SHRM methodology."
    ),
    "departmentSummary": [
        {"group_value": "Engineering",        "total_records": 142, "average_risk_score": 67.2, "average_stability_score": 45.1, "priority_review_count": 28, "strategic_concern_count": 34, "monitoring_count": 41, "stable_count": 39, "department_recommendations": ["Initiate bi-weekly 1:1 reviews for at-risk engineers", "Review compensation benchmarking against market"]},
        {"group_value": "Operations",         "total_records": 198, "average_risk_score": 58.9, "average_stability_score": 52.4, "priority_review_count": 21, "strategic_concern_count": 38, "monitoring_count": 67, "stable_count": 72, "department_recommendations": ["Deploy structured career pathway programme"]},
        {"group_value": "Customer Experience","total_records": 115, "average_risk_score": 54.1, "average_stability_score": 57.2, "priority_review_count": 18, "strategic_concern_count": 24, "monitoring_count": 39, "stable_count": 34, "department_recommendations": ["Implement role rotation and skills development"]},
        {"group_value": "Finance",            "total_records": 87,  "average_risk_score": 42.0, "average_stability_score": 68.3, "priority_review_count": 12, "strategic_concern_count": 18, "monitoring_count": 29, "stable_count": 28, "department_recommendations": ["Monitor workload distribution"]},
        {"group_value": "HR & People",        "total_records": 63,  "average_risk_score": 38.7, "average_stability_score": 72.1, "priority_review_count": 8,  "strategic_concern_count": 9,  "monitoring_count": 17, "stable_count": 29, "department_recommendations": ["Retain key HR business partners"]},
        {"group_value": "Technology",         "total_records": 105, "average_risk_score": 35.2, "average_stability_score": 76.5, "priority_review_count": 5,  "strategic_concern_count": 4,  "monitoring_count": 10, "stable_count": 86, "department_recommendations": ["Continue current engagement initiatives"]},
    ],
    "executiveIndices": {
        "wsi": 62.4, "wsi_grade": "C", "wsi_interpretation_en": "Below threshold. Workforce stability requires intervention.",
        "hcri": 41.3, "hcri_grade": "D", "hcri_interpretation_en": "Elevated human capital risk detected.",
        "tfri": 55.0, "tfri_grade": "C",
        "lsi": 68.2, "lsi_grade": "B",
        "ori": 44.1, "ori_grade": "D",
        "rhi": 38.9, "rhi_grade": "D",
        "headline_en": "26.1% of the workforce is at elevated risk, representing SAR 26.5M in financial exposure.",
        "headline_ar": "26.1% من القوى العاملة في نطاق خطر مرتفع، مما يمثل تعرضاً مالياً بقيمة 26.5 مليون ريال.",
    },
    "executiveRoi": {
        "available": True,
        "total_annual_exposure_low_sar": 22_400_000,
        "total_annual_exposure_high_sar": 31_200_000,
        "roi_scenarios": [
            {"scenario": "Minimal", "total_savings_low_sar": 2_800_000, "total_savings_high_sar": 4_200_000, "estimated_roi_pct_low": 180, "estimated_roi_pct_high": 270},
            {"scenario": "Targeted", "total_savings_low_sar": 7_200_000, "total_savings_high_sar": 11_400_000, "estimated_roi_pct_low": 340, "estimated_roi_pct_high": 520},
            {"scenario": "Full Programme", "total_savings_low_sar": 14_600_000, "total_savings_high_sar": 19_800_000, "estimated_roi_pct_low": 680, "estimated_roi_pct_high": 940},
        ],
    },
    "decisionIntelligence": {
        "available": True,
        "decision_readiness_level": "high",
        "executive_priority_score": 87,
        "board_summary_en": "Immediate workforce stabilisation required. 221 employees at risk, SAR 26.5M exposure.",
        "strategic_priorities": [
            {"priority_en": "Commission an immediate workforce stabilisation programme for Engineering and Operations, targeting the 62 Priority Review employees within 30 days.", "priority_ar": "تفويض برنامج استقرار قوى عاملة فوري للهندسة والعمليات.", "urgency": "CRITICAL", "confidence": "high", "confidence_reason_en": "High confidence based on 12 matched constructs.", "supporting_metrics": "62 employees in Priority Review; SAR 7.4M direct exposure in these two departments."},
            {"priority_en": "Establish a quarterly workforce intelligence reporting cadence to the Board with financial exposure trending.", "priority_ar": "إنشاء دورية تقارير ذكاء القوى العاملة الفصلية لمجلس الإدارة.", "urgency": "HIGH", "confidence": "high", "confidence_reason_en": "Board governance best practice.", "supporting_metrics": "Board-level visibility on workforce risk is currently absent."},
            {"priority_en": "Deploy targeted retention interventions in Customer Experience before Q3 headcount review.", "priority_ar": "تنفيذ تدخلات احتفاظ موجّهة في تجربة العملاء قبل مراجعة الموارد البشرية للربع الثالث.", "urgency": "HIGH", "confidence": "medium", "confidence_reason_en": "Medium confidence — department data partially matched.", "supporting_metrics": "42 employees in Strategic Concern or Priority Review in CX."},
        ],
        "top_decision_questions": [
            {"question_en": "Which departments should be prioritised for immediate intervention?", "answer_en": "Engineering (67.2 avg risk) and Operations (58.9 avg risk) require immediate action.", "confidence": "high", "governance_note": "Based on statistical risk scores. HR review required."},
        ],
        "department_decision_briefs": [
            {"department": "Engineering", "risk_level": "High", "main_driver": "Workload imbalance", "recommended_action": "Bi-weekly 1:1 and compensation review", "confidence": "high", "governance_note": "Statistical. HR review required."},
        ],
        "limitations": [
            "Statistical associations, not causal certainty.",
            "Qualified HR professional review required before any employment action.",
            "PDPL-compliant. No personal identifiers processed.",
        ],
        "evidence_pack": {
            "conservative_ml_summary": "VotingEnsemble: ROC-AUC 0.8471, MCC 0.4942, F1 0.7073",
            "top_features": ["stability_score", "engagement_index", "performance_trend"],
            "top_risk_drivers": ["low_engagement", "overwork", "career_stagnation"],
        },
    },
    "storytelling": {
        "available": True,
        "board_narrative": {
            "headline_en": "26% of STC's workforce is in an elevated-risk stability zone — a SAR 26.5M financial exposure requiring board-level authorisation.",
            "headline_ar": "26% من قوى عمل STC في منطقة استقرار مرتفعة المخاطر — تعرض مالي بقيمة 26.5 مليون ريال يستلزم تفويضاً من مجلس الإدارة.",
            "key_finding_en": "Engineering and Operations departments concentrate 62% of Priority Review employees despite representing only 40% of total headcount. Without intervention, monthly attrition cost is estimated at SAR 2.2M.",
            "key_finding_ar": "تركّز قسما الهندسة والعمليات 62% من موظفي الأولوية القصوى رغم تمثيلهم 40% فقط من إجمالي القوى العاملة.",
            "recommended_action_en": "Authorise a 90-day Workforce Stabilisation Programme with monthly board progress reporting.",
            "recommended_action_ar": "تفويض برنامج استقرار قوى عاملة لـ 90 يوماً مع تقارير شهرية لمجلس الإدارة.",
            "governance_note": "Statistical indicators only. Not for individual employment decisions. PDPL-compliant.",
        },
        "ceo_narrative": {
            "headline_en": "One in four STC employees is in a risk band that, if unaddressed, will cost the organisation SAR 2.2M per month.",
            "headline_ar": "واحد من كل أربعة موظفين في STC في نطاق مخاطر سيكلف المنظمة 2.2 مليون ريال شهرياً إذا لم يُعالَج.",
            "key_finding_en": "The highest-risk concentration is in Engineering — a department critical to STC's digital transformation agenda. Intervention within this quarter can recover SAR 9.3M in potential savings.",
            "key_finding_ar": "أعلى تركيز للمخاطر في قسم الهندسة — القسم الحيوي لأجندة التحول الرقمي لـ STC.",
        },
        "chro_narrative": {
            "headline_en": "HR has a 30-day window to deploy targeted interventions for 62 Priority Review employees before Q3 headcount consolidation.",
            "headline_ar": "لدى الموارد البشرية 30 يوماً لتنفيذ تدخلات موجّهة لـ 62 موظفاً قبل توطيد القوى العاملة في الربع الثالث.",
        },
    },
    "orgRiskDriverSummary": {
        "top_org_risk_drivers": [
            {"driver_name": "Workload Imbalance", "employee_count": 143, "avg_risk_score": 68.2},
            {"driver_name": "Career Stagnation", "employee_count": 98,  "avg_risk_score": 61.4},
        ],
        "top_org_protective_factors": [
            {"driver_name": "Strong Team Cohesion", "employee_count": 312, "avg_stability_score": 81.3},
        ],
    },
    "modelMetrics": {
        "available": True,
        "source": "VotingEnsemble (CatBoost + RandomForest + GradientBoosting)",
        "rocAuc": 0.8471, "mcc": 0.4942, "f1Score": 0.7073,
        "precision": 0.7240, "recall": 0.6932, "accuracy": 0.7523,
        "brierScore": 0.1821, "calibrationError": 0.0379, "optimalThreshold": 0.48,
        "confusionMatrix": {"tp": 412, "tn": 223, "fp": 98, "fn": 114},
    },
    "mlValidation": {"available": False, "reason": "No target column in dataset"},
    "simulationResult": {"available": False},
    "persistenceInfo": {"saved": True, "session_id": "PROOF-2026-06-02"},
}


def run():
    print("=" * 60)
    print("PHASE 33 - PROOF GENERATION")
    print("=" * 60)
    print()

    # ── 1. PPTX ────────────────────────────────────────────────────
    print("[1] Generating PPTX...")
    from backend.core.executive_pptx_exporter import generate_pptx
    from pptx import Presentation

    pptx_bytes = generate_pptx(REALISTIC_DATA, company_name="STC — Workforce Intelligence")
    pptx_path  = Path(__file__).parent / "PROOF_AWI_Executive_Board_Deck.pptx"
    pptx_path.write_bytes(pptx_bytes)
    print(f"  OK File written: {pptx_path.name}  ({len(pptx_bytes):,} bytes)")

    # Verify open
    prs = Presentation(io.BytesIO(pptx_bytes))
    slide_count = len(prs.slides)
    print(f"  OK python-pptx opened successfully: {slide_count} slides")
    for i, slide in enumerate(prs.slides, 1):
        titles = [
            sh.text_frame.text.strip()
            for sh in slide.shapes
            if sh.has_text_frame and sh.text_frame.text.strip()
        ]
        first = titles[0] if titles else "(no text)"
        print(f"    Slide {i:02d}: {first[:70]}")
    assert slide_count == 12, f"Expected 12 slides, got {slide_count}"
    print(f"  OK Slide count verified: {slide_count} == 12")
    print()

    # ── 2. HTML Slide Deck ─────────────────────────────────────────
    print("[2] Generating HTML Board Briefing Document...")
    from backend.core.executive_slide_exporter import generate_slide_deck

    html = generate_slide_deck(REALISTIC_DATA, company_name="STC — Workforce Intelligence")
    html_path = Path(__file__).parent / "PROOF_AWI_Board_Briefing.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  OK File written: {html_path.name}  ({len(html):,} chars)")

    page_count = html.count('class="slide')
    footer_count = html.count("/ 11")
    print(f"  OK Slide divs found: {page_count}")
    print(f"  OK Footer markers '/ 11' found: {footer_count}")
    assert page_count >= 11, f"Expected >=11 slide divs, got {page_count}"
    assert "/ 11" in html, "Footer '/ 11' not found in HTML"
    print(f"  OK Page structure verified: {page_count} pages, footer '/ 11'")
    print()

    # ── 3. Structure checks ────────────────────────────────────────
    print("[3] Content verification...")

    # HTML checks
    assert "Board Briefing" in html or "BOARD BRIEFING" in html or "AWI" in html, "Missing board branding"
    assert "SAR" in html, "Missing SAR financial figures"
    assert "SHRM" in html, "Missing SHRM attribution"
    assert "PDPL" in html, "Missing PDPL compliance note"
    print("  OK HTML: Board branding, SAR figures, SHRM attribution, PDPL compliance - all present")

    # PPTX checks
    full_text = " ".join(
        sh.text_frame.text for slide in prs.slides for sh in slide.shapes if sh.has_text_frame
    )
    assert "SAR" in full_text, "PPTX missing SAR figures"
    assert "SHRM" in full_text or "Conservative" in full_text, "PPTX missing methodology attribution"
    print("  OK PPTX: SAR figures, Conservative methodology - all present")
    print()

    # ── 4. Summary ────────────────────────────────────────────────
    print("=" * 60)
    print("PROOF SUMMARY")
    print("=" * 60)
    print(f"  PPTX file:    {pptx_path.name}")
    print(f"  PPTX size:    {len(pptx_bytes):,} bytes")
    print(f"  PPTX slides:  {slide_count} (required: 12)  PASS")
    print(f"  HTML file:    {html_path.name}")
    print(f"  HTML size:    {len(html):,} chars")
    print(f"  HTML pages:   {page_count} (required: 11)  PASS")
    print(f"  Generated:    {datetime.now().isoformat()}")
    print()
    print("  ALL PROOF CHECKS PASSED")
    print("=" * 60)

    return {
        "pptx_path": str(pptx_path),
        "pptx_bytes": len(pptx_bytes),
        "pptx_slides": slide_count,
        "html_path": str(html_path),
        "html_chars": len(html),
        "html_pages": page_count,
    }


if __name__ == "__main__":
    result = run()
    print()
    print(json.dumps(result, indent=2))
