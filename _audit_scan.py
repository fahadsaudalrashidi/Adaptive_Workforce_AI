import sys, re, os
sys.path.insert(0, ".")

forbidden = {
    "hardcoded_usd":   ["financial_exposure_usd", "total_financial_exposure_usd"],
    "causal_language": ["causes attrition", "will leave", "guaranteed to leave", "must intervene"],
    "stack_trace_ui":  ["st.exception", "traceback.print_exc"],
    "fake_dept":       ["All Employees"],
}

issues = {}
for dp, dns, fns in os.walk("."):
    dns[:] = [d for d in dns if d not in ["__pycache__", ".git"]]
    for fn in fns:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dp, fn)
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for cat, patterns in forbidden.items():
            for pat in patterns:
                for i, line in enumerate(lines, 1):
                    if pat.lower() in line.lower():
                        key = f"{path}:{i}"
                        issues[key] = f"[{cat}] {line.strip()[:100]}"

if issues:
    print(f"{len(issues)} issues found:")
    for k, v in sorted(issues.items()):
        print(f"  {k}: {v}")
else:
    print("No forbidden patterns found.")

# Check confidence_governance import in app.py
with open("frontend/app.py", encoding="utf-8") as f:
    app_src = f.read()

checks = {
    "ConfidenceGovernor imported": "ConfidenceGovernor" in app_src,
    "FeatureTrustworthinessAssessor imported": "FeatureTrustworthinessAssessor" in app_src,
    "HUMAN_OVERSIGHT_DISCLAIMER imported": "HUMAN_OVERSIGHT_DISCLAIMER" in app_src,
    "DEFAULT_CURRENCY imported": "DEFAULT_CURRENCY" in app_src,
    "unified_confidence in session_state": "unified_confidence" in app_src,
    "feature_trust in session_state": "feature_trust" in app_src,
    "mask_employee_ids in session_state": "mask_employee_ids" in app_src,
    "demo_mode in session_state": "demo_mode" in app_src,
    "_render_unified_confidence_panel defined": "_render_unified_confidence_panel" in app_src,
    "_render_feature_trust_panel defined": "_render_feature_trust_panel" in app_src,
}

print("\nApp.py governance checks:")
for k, v in checks.items():
    print(f"  {'OK' if v else 'MISSING':7s} {k}")
