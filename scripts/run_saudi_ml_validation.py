"""
Run real ML validation on the Saudi attrition dataset.

Usage:  py scripts/run_saudi_ml_validation.py

Exits 0 if ML validation is available, 1 if unavailable or file not found.
No internet required. No frontend required.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd

from backend.core.ml_validation_engine import run_ml_validation

# ── Locate the Saudi attrition dataset ───────────────────────────────────────

_CANDIDATE_DIRS = [
    Path(r"C:\Users\PvP-Pc\Desktop\datasetssaudi"),
    Path(r"C:\Users\PvP-Pc\Desktop"),
    _ROOT / "data",
    _ROOT / "datasets",
]

_CANDIDATE_PATTERNS = [
    "Original Dataset of Employee Attrition (1).xlsx",
    "Original Dataset of Employee Attrition*.xlsx",
    "*Attrition*.xlsx",
    "*Employee Attrition*.xlsx",
    "*attrition*.xlsx",
]


def _find_dataset() -> Path | None:
    for d in _CANDIDATE_DIRS:
        if not d.exists():
            continue
        for pattern in _CANDIDATE_PATTERNS:
            matches = sorted(d.glob(pattern))
            if matches:
                return matches[0]
    return None


def _fmt(v, decimals=4) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def main() -> int:
    dataset_path = _find_dataset()
    if dataset_path is None:
        print("ERROR: Could not locate Saudi attrition dataset.")
        print("Searched directories:", [str(d) for d in _CANDIDATE_DIRS])
        return 1

    print(f"\nDataset found: {dataset_path}")
    print("Loading dataset...")

    if dataset_path.suffix.lower() == ".xlsx":
        df = pd.read_excel(dataset_path)
    else:
        df = pd.read_csv(dataset_path)

    print(f"Loaded {len(df):,} rows × {len(df.columns)} columns")
    print("Running ML validation (this may take 10–30 seconds)...\n")

    result = run_ml_validation(df)

    sep = "=" * 60

    # ── Dataset summary ───────────────────────────────────────────────────────
    print(sep)
    print("DATASET")
    print(sep)
    print(f"  File:            {dataset_path.name}")
    print(f"  Row count:       {len(df):,}")
    print(f"  Column count:    {len(df.columns)}")
    print(f"  Target column:   {result.get('target_column') or '— (none detected)'}")
    print(f"  n_samples:       {result['n_samples']:,}")
    print(f"  n_train:         {result['n_train']:,}")
    print(f"  n_test:          {result['n_test']:,}")
    print(f"  n_positive:      {result['n_positive']:,}")
    print(f"  n_negative:      {result['n_negative']:,}")

    if not result["available"]:
        print(f"\nML validation UNAVAILABLE: {result['reason']}")
        return 1

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION A — ORIGINAL FULL-FEATURE RESULTS
    # ═══════════════════════════════════════════════════════════════════════════
    proxy_warning = result.get("original_has_proxy_warning", False)

    print(f"\n{sep}")
    print("SECTION A — ORIGINAL FULL-FEATURE RESULTS")
    if proxy_warning:
        print("  *** PROXY LEAKAGE WARNING: Metrics likely inflated by tenure/experience features ***")
    print(sep)

    print(f"  Best model:  {result['best_model']}")

    sm = result["selected_metrics"] or {}
    print(f"\n  ROC-AUC:           {_fmt(sm.get('roc_auc'), 4)}")
    print(f"  MCC:               {_fmt(sm.get('mcc'), 4)}")
    print(f"  F1-score:          {_fmt(sm.get('f1_score'), 4)}")
    acc = sm.get("accuracy")
    print(f"  Accuracy:          {f'{acc*100:.2f}%' if acc is not None else '—'}")
    print(f"  Precision:         {_fmt(sm.get('precision'), 4)}")
    print(f"  Recall:            {_fmt(sm.get('recall'), 4)}")
    print(f"  Brier Score:       {_fmt(sm.get('brier_score'), 4)}")
    print(f"  Calibration Error: {_fmt(sm.get('calibration_error'), 4)}")
    print(f"  Optimal Threshold: {_fmt(sm.get('optimal_threshold'), 2)}")

    print(f"\n  All model results:")
    for m in result["model_results"]:
        best_marker = " *" if m["model_name"] == result["best_model"] else "  "
        if "error" in m:
            print(f"  {best_marker} {m['model_name']:30s}  ERROR: {m['error']}")
        else:
            acc_val = m.get("accuracy")
            acc_str = f"{acc_val*100:.1f}%" if acc_val is not None else "—"
            print(
                f"  {best_marker} {m['model_name']:30s}"
                f"  AUC={_fmt(m.get('roc_auc'), 4)}"
                f"  MCC={_fmt(m.get('mcc'), 4)}"
                f"  F1={_fmt(m.get('f1_score'), 4)}"
                f"  Acc={acc_str}"
            )

    cm = result.get("confusion_matrix")
    print(f"\n  Confusion matrix (at optimal threshold):")
    if cm:
        print(f"    TP: {cm['tp']:>5}    FP: {cm['fp']:>5}")
        print(f"    FN: {cm['fn']:>5}    TN: {cm['tn']:>5}")
    else:
        print("    Not available")

    fi = result.get("feature_importance", [])
    print(f"\n  Top 10 feature importance:")
    if fi:
        for f in fi[:10]:
            bar = "#" * int(f["importance"] / fi[0]["importance"] * 20) if fi[0]["importance"] > 0 else ""
            print(f"    #{f['rank']:>2}  {f['feature']:<35}  {f['importance']:.6f}  {bar}")
    else:
        print("    Not available")

    # ═══════════════════════════════════════════════════════════════════════════
    # SECTION B — CONSERVATIVE PROXY-CONTROLLED RESULTS (RECOMMENDED ACADEMIC)
    # ═══════════════════════════════════════════════════════════════════════════
    con = result.get("conservative")
    print(f"\n{sep}")
    print("SECTION B — CONSERVATIVE PROXY-CONTROLLED RESULTS")
    print("  *** RECOMMENDED ACADEMIC REPORTING METRICS ***")
    print(f"  Method: 5-fold StratifiedKFold CV, threshold=0.50")
    print(sep)

    if con is None:
        print("  Not computed.")
    elif not con.get("available", False):
        print(f"  Unavailable: {con.get('reason', 'unknown reason')}")
    else:
        removed = con.get("removed_proxy_features", [])
        print(f"  Proxy features removed ({len(removed)}): {', '.join(removed) if removed else 'none'}")
        print(f"  Clean feature count:   {con.get('clean_feature_count', '—')}")
        print(f"  Dataset difficulty:    {con.get('dataset_difficulty', '—')}")
        print(f"  Best model:            {con.get('best_model', '—')}")

        con_sm = con.get("selected_metrics") or {}
        mean_auc = con_sm.get("mean_roc_auc")
        std_auc  = con_sm.get("std_roc_auc")
        fold_aucs = con_sm.get("fold_aucs", [])

        print(f"\n  Mean ROC-AUC:      {_fmt(mean_auc, 4)}  (std={_fmt(std_auc, 4)})")
        print(f"  Mean MCC:          {_fmt(con_sm.get('mean_mcc'), 4)}  (std={_fmt(con_sm.get('std_mcc'), 4)})")
        print(f"  Mean F1-score:     {_fmt(con_sm.get('mean_f1_score'), 4)}  (std={_fmt(con_sm.get('std_f1_score'), 4)})")
        mean_acc = con_sm.get("mean_accuracy")
        print(f"  Mean Accuracy:     {f'{mean_acc*100:.2f}%' if mean_acc is not None else '—'}  (std={_fmt(con_sm.get('std_accuracy'), 4)})")
        print(f"  Mean Precision:    {_fmt(con_sm.get('mean_precision'), 4)}  (std={_fmt(con_sm.get('std_precision'), 4)})")
        print(f"  Mean Recall:       {_fmt(con_sm.get('mean_recall'), 4)}  (std={_fmt(con_sm.get('std_recall'), 4)})")
        if fold_aucs:
            fold_str = "  ".join(f"{a:.4f}" for a in fold_aucs)
            print(f"  Per-fold AUCs:     {fold_str}")

        print(f"\n  CV model comparison:")
        for m in con.get("cv_results", []):
            best_marker = " *" if m["model_name"] == con.get("best_model") else "  "
            if "error" in m:
                print(f"    {best_marker} {m['model_name']:30s}  ERROR: {m['error']}")
            else:
                print(
                    f"    {best_marker} {m['model_name']:30s}"
                    f"  AUC={_fmt(m.get('mean_roc_auc'), 4)}+/-{_fmt(m.get('std_roc_auc'), 4)}"
                    f"  F1={_fmt(m.get('mean_f1_score'), 4)}"
                )

        con_cm = con.get("oof_confusion_matrix")
        print(f"\n  OOF confusion matrix (threshold=0.50):")
        if con_cm:
            print(f"    TP: {con_cm['tp']:>5}    FP: {con_cm['fp']:>5}")
            print(f"    FN: {con_cm['fn']:>5}    TN: {con_cm['tn']:>5}")
        else:
            print("    Not available")

        con_fi = con.get("feature_importance", [])
        print(f"\n  Top 15 feature importance (proxy-free):")
        if con_fi:
            for f in con_fi[:15]:
                bar = "#" * int(f["importance"] / con_fi[0]["importance"] * 20) if con_fi[0]["importance"] > 0 else ""
                print(f"    #{f['rank']:>2}  {f['feature']:<35}  {f['importance']:.6f}  {bar}")
        else:
            print("    Not available")

        for w in con.get("feature_importance_warnings", []):
            print(f"\n  *** {w}")

    # ── Governance ────────────────────────────────────────────────────────────
    gov = result.get("governance", {})
    print(f"\n{sep}")
    print("GOVERNANCE")
    print(sep)
    pii = gov.get("pii_columns_removed", [])
    leakage = gov.get("leakage_columns_removed", [])
    identifiers = gov.get("identifier_columns_removed", [])
    excluded = gov.get("excluded_columns", [])
    warnings = gov.get("ml_governance_warnings", [])

    print(f"  Feature count:              {gov.get('feature_count', '—')}")
    print(f"  PII columns removed:        {pii if pii else 'none'}")
    print(f"  Identifier cols removed:    {identifiers if identifiers else 'none'}")
    print(f"  Leakage cols removed:       {leakage if leakage else 'none'}")
    print(f"  All excluded cols:          {excluded if excluded else 'none'}")
    print(f"\n  Governance warnings ({len(warnings)}):")
    for w in warnings:
        print(f"    · {w}")

    print(f"\n{sep}")
    print("ML VALIDATION COMPLETE — available=True")
    print(sep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
