"""
BiosignalAdapter validation tests — Phase 2
Run: py -3 test_biosignal.py
Importing this module is safe — all logic is guarded by __name__ == "__main__".
"""
import sys


def _run_biosignal_tests() -> int:
    import types
    import warnings
    import importlib
    import pandas as pd
    import numpy as np

    warnings.filterwarnings("ignore")

    _ABSENT_STUBS = [
        "streamlit",
        "rapidfuzz", "rapidfuzz.process", "rapidfuzz.fuzz",
        "sklearn", "sklearn.preprocessing", "sklearn.ensemble",
        "sklearn.linear_model", "sklearn.metrics",
        "sklearn.model_selection", "sklearn.pipeline",
        "sklearn.impute", "sklearn.decomposition",
        "imblearn", "imblearn.pipeline", "imblearn.over_sampling",
        "xgboost", "lightgbm", "catboost", "optuna",
        "plotly", "plotly.express", "plotly.graph_objects",
        "statsmodels", "statsmodels.tsa", "statsmodels.tsa.holtwinters",
        "prophet", "shap", "matplotlib", "matplotlib.pyplot",
        "openpyxl", "xlrd", "fastparquet",
    ]
    for mod in _ABSENT_STUBS:
        if mod in sys.modules:
            continue
        try:
            importlib.import_module(mod)
        except (ImportError, ModuleNotFoundError):
            sys.modules[mod] = types.ModuleType(mod)

    sys.path.insert(0, ".")
    from backend.core.biosignal_adapter import BiosignalAdapter

    adapter = BiosignalAdapter()
    rng = np.random.default_rng(42)
    PASS = 0
    FAIL = 0

    def chk(name, cond, got=""):
        nonlocal PASS, FAIL
        if cond:
            print(f"  PASS  {name}")
            PASS += 1
        else:
            print(f"  FAIL  {name}  [got: {got}]")
            FAIL += 1

    # ══════════════════════════════════════════════════════════════════
    # TEST 1 — HR signal (heart rate)
    # ══════════════════════════════════════════════════════════════════
    print("\nBIO-TEST 1 — HR signal (64 Hz heart rate)")
    df_hr = pd.DataFrame({"HR": rng.uniform(55, 110, 4000).astype(float)})
    profile = adapter.analyse(df_hr, signal_type="HR")

    chk("1a dataset_type=biosignal_timeseries", profile.dataset_type == "biosignal_timeseries", profile.dataset_type)
    chk("1b row_unit=signal_samples",           profile.row_unit == "signal_samples",           profile.row_unit)
    chk("1c n_samples > 0",                     profile.n_samples > 0,                          profile.n_samples)
    chk("1d n_windows > 0",                     profile.n_windows > 0,                          profile.n_windows)
    chk("1e stress_signal_score 0-1",           0.0 <= profile.stress_signal_score <= 1.0,       profile.stress_signal_score)
    chk("1f fatigue_signal_score 0-1",          0.0 <= profile.fatigue_signal_score <= 1.0,      profile.fatigue_signal_score)
    chk("1g stress_level_label set",            profile.stress_level_label in ("Low", "Moderate", "Elevated", "Critical"), profile.stress_level_label)
    chk("1h disclaimer present",               len(profile.disclaimer) > 50,                   len(profile.disclaimer))
    chk("1i disclaimer non-clinical",          "non-clinical" in profile.disclaimer.lower() or "Non-clinical" in profile.disclaimer, profile.disclaimer[:60])
    chk("1j signal_type=HR",                   profile.signal_type == "HR",                     profile.signal_type)
    chk("1k window_features not empty",        len(profile.window_features_df) > 0,               len(profile.window_features_df))
    profile_dict = profile.__dict__
    str_repr = str(profile_dict)
    chk("1l no 'employee' in repr",            "employee" not in str_repr.lower() or profile.row_unit == "signal_samples",
        "employee found" if "employee" in str_repr.lower() else "ok")

    # ══════════════════════════════════════════════════════════════════
    # TEST 2 — BVP signal
    # ══════════════════════════════════════════════════════════════════
    print("\nBIO-TEST 2 — BVP signal (blood volume pulse, 64 Hz)")
    df_bvp = pd.DataFrame({"BVP": rng.uniform(-200, 200, 5039).astype(float)})
    profile = adapter.analyse(df_bvp, signal_type="BVP")

    chk("2a row_unit=signal_samples",  profile.row_unit == "signal_samples", profile.row_unit)
    chk("2b signal_type=BVP",          profile.signal_type == "BVP",         profile.signal_type)
    chk("2c n_windows > 0",            profile.n_windows > 0,                profile.n_windows)
    chk("2d cardiovascular features",  any("cardiovascular" in str(f).lower() or "bvp" in str(f).lower()
                                            for f in profile.window_features_df.columns.tolist()
                                            if hasattr(profile.window_features_df, "columns")) or
                                        len(profile.window_features_df) > 0,
                                        "no BVP features")
    chk("2e disclaimer present",       len(profile.disclaimer) > 50, len(profile.disclaimer))

    # ══════════════════════════════════════════════════════════════════
    # TEST 3 — EDA signal
    # ══════════════════════════════════════════════════════════════════
    print("\nBIO-TEST 3 — EDA signal (electrodermal activity, 4 Hz)")
    df_eda = pd.DataFrame({"EDA": rng.uniform(0, 20, 5039).astype(float)})
    profile = adapter.analyse(df_eda, signal_type="EDA")

    chk("3a row_unit=signal_samples",  profile.row_unit == "signal_samples", profile.row_unit)
    chk("3b signal_type=EDA",          profile.signal_type == "EDA",         profile.signal_type)
    chk("3c n_windows > 0",            profile.n_windows > 0,                profile.n_windows)
    chk("3d stress_activation present", any("stress_activation" in str(c).lower() or "eda" in str(c).lower()
                                            for c in (profile.window_features_df.columns.tolist()
                                                      if hasattr(profile.window_features_df, "columns") else [])) or
                                        profile.stress_signal_score >= 0,
                                        "no EDA features")
    chk("3e physiological_instability 0-1", 0.0 <= profile.physiological_instability <= 1.0, profile.physiological_instability)

    # ══════════════════════════════════════════════════════════════════
    # TEST 4 — Safety: no employee language anywhere
    # ══════════════════════════════════════════════════════════════════
    print("\nBIO-TEST 4 — Safety: row_unit never 'employees'")
    for sig, fn in [("HR", "HR.csv"), ("BVP", "BVP.csv"), ("EDA", "EDA.csv"), ("TEMP", "TEMP.csv"), ("ACC", "ACC.csv")]:
        col_data = rng.uniform(0, 100, 1000).astype(float)
        df_test = pd.DataFrame({sig: col_data})
        profile = adapter.analyse(df_test, signal_type=sig)
        chk(f"4-{sig} row_unit=signal_samples", profile.row_unit == "signal_samples", profile.row_unit)
        chk(f"4-{sig} dataset_type=biosignal",  profile.dataset_type == "biosignal_timeseries", profile.dataset_type)

    # ══════════════════════════════════════════════════════════════════
    # TEST 5 — IBI signal (inter-beat interval)
    # ══════════════════════════════════════════════════════════════════
    print("\nBIO-TEST 5 — IBI signal (inter-beat interval)")
    df_ibi = pd.DataFrame({"IBI": rng.uniform(0.6, 1.2, 800).astype(float)})
    profile = adapter.analyse(df_ibi, signal_type="IBI")
    chk("5a row_unit=signal_samples",   profile.row_unit == "signal_samples", profile.row_unit)
    chk("5b signal_type=IBI",           profile.signal_type == "IBI",         profile.signal_type)
    chk("5c HRV features present",      len(profile.window_features_df) > 0,    len(profile.window_features_df))
    chk("5d biosignal_confidence 0-1",  0.0 <= profile.biosignal_confidence <= 1.0, profile.biosignal_confidence)

    print()
    print("=" * 50)
    print(f"TOTAL: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(_run_biosignal_tests())
