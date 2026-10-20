# Report Consistency Audit
**Platform:** Adaptive Workforce Intelligence Engine v2.5.1  
**Audit Date:** 2026-05-20  
**Scope:** Language safety, version consistency, forbidden phrase enforcement

---

## Summary

| Category | Issues Found | Status |
|----------|-------------|--------|
| Forbidden executive phrases | 0 violations | ✅ CLEAN (22 phrases enforced) |
| "increases risk" / "decreases risk" language | Fixed in v2.5.1 | ✅ FIXED |
| "high-risk employees" label | Fixed in v2.5.1 | ✅ FIXED |
| "employees require immediate" imperative | Fixed in v2.5.1 | ✅ FIXED |
| "individual risk scores are highly reliable" overclaim | Fixed in v2.5.1 | ✅ FIXED |
| Version consistency (v2.3 hardcoding) | Fixed in v2.5.1 | ✅ FIXED |
| Currency hardcoding (USD) | Previously fixed in v2.4.x | ✅ CLEAN |

---

## Language Changes Made (v2.5.1)

### report_generator.py

| Old (Forbidden) | New (Safe) | Location |
|----------------|-----------|---------|
| `↑ increases risk` | `↑ associated with elevated predicted risk` | `_generate_hr_report()` Top Predictive Drivers |
| `↓ decreases risk` | `↓ associated with lower predicted risk` | `_generate_hr_report()` Top Predictive Drivers |
| `Strongest predictor: '...' is associated...` | `Top statistical driver: '...' shows the strongest association...` | `_extract_hr_findings()` |
| `High Risk` (distribution label) | `Priority Review` | Attrition Risk Summary labels |
| `Individual predictions require human validation.` | `Individual predictions require human validation before any HR action.` | Attrition Risk Summary caveats |

### insight_generator.py

| Old (Forbidden) | New (Safe) | Location |
|----------------|-----------|---------|
| `Critical Organisational Attrition Risk` | `Critical Organisational Attrition Signal` | HR insight title |
| `are classified as High or Critical risk` | `are in the priority review segment` | HR insight body |
| `Immediately convene HR leadership and deploy...` | `Convene HR leadership to review priority-segment employees — no automated action` | HR insight action |
| `employees are flagged as high risk` | `employees are flagged for structured HR review` | Elevated risk insight |
| `individual risk scores are highly reliable` | Removed overclaim — added governance caveat | High-AUC opportunity insight |
| `employees require immediate retention attention` | `employees in the priority review segment — human validation required` | Executive summary |
| `The workforce is at X% predicted attrition risk` | `The workforce shows X% predicted attrition probability` | Executive summary |

---

## FORBIDDEN_EXECUTIVE_PHRASES Status

All 22 entries in `config.settings.FORBIDDEN_EXECUTIVE_PHRASES` are enforced:

```
terminate, terminated, termination
fire , fires , fired
dismiss, dismissed, dismissal
layoff, lay off, lay-off
redundant, made redundant
will leave, will resign, will quit
certain to leave, guaranteed to leave
must be removed, should be removed
eliminate this employee
```

**Test coverage:** `tests/test_executive_language.py` — 21 tests, all passing.

---

## ATTRITION_LANGUAGE_SAFE Map (Updated v2.5.1)

New entries added to `config/settings.py`:

| Unsafe | Safe Replacement |
|--------|-----------------|
| `increases risk` | `associated with elevated predicted risk` |
| `decreases risk` | `associated with lower predicted risk` |
| `high-risk employees` | `employees in the priority review segment` |
| `require immediate retention` | `flagged for structured retention review` |

---

## Version Consistency

| File | Old Version | New Version | Method |
|------|------------|-------------|--------|
| `config/settings.py` | 2.3.0 | 2.5.1 | Direct update |
| `PLATFORM_VERSION` | "2.3.0" | "2.5.1" | Single source of truth |
| `REPORT_VERSION` | "2.3" | "2.5" | Single source of truth |
| `MODEL_VERSION` | "2.3.0" | "2.5.1" | Single source of truth |

All report headers, HTML footers, and plain-text reports import from `config.settings` —
no hardcoded version strings remain in report_generator.py or insight_generator.py.

---

## Remaining Acceptable Uses

The following are NOT forbidden and may appear in output:
- "associated with predicted risk" — associative, not causal
- "priority review segment" — replaces "high-risk employees"
- "elevated predicted risk" — factual probability claim, not deterministic
- "for HR review" / "requires human validation" — appropriate governance language
- "may indicate" — appropriately hedged language
