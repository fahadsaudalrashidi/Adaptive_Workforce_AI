"""
Biosignal Adapter v2 — Full Physiological Signal Intelligence

Processes WESAD / Empatica / wearable signal CSVs with window-based feature
extraction and multi-layer scoring. Rows are SIGNAL SAMPLES, not employees.
Never uses employee terminology; all output uses "samples", "windows", "signal".

Supported signals: HR, EDA, BVP, TEMP, ACC, IBI, ECG, EEG, EMG, PPG
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import signal as sp_signal
    from scipy import stats as sp_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL SPECIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SignalSpec:
    canonical: str       # display name
    unit: str
    typical_fs: float    # Hz (0 = unknown)
    normal_low: float
    normal_high: float
    stress_direction: str  # "up" or "down" (which end = stress)
    description: str


SIGNAL_REGISTRY: Dict[str, SignalSpec] = {
    "HR":   SignalSpec("Heart Rate", "bpm", 1.0,   50, 100, "up",
                       "Heart rate in beats per minute"),
    "EDA":  SignalSpec("Electrodermal Activity", "µS", 4.0, 0, 10, "up",
                       "Skin conductance — sympathetic nervous system arousal"),
    "BVP":  SignalSpec("Blood Volume Pulse", "raw", 64.0, -500, 500, "up",
                       "Peripheral blood volume pulse from PPG sensor"),
    "TEMP": SignalSpec("Skin Temperature", "°C", 4.0, 30, 38, "down",
                       "Wrist skin temperature — decreases under sympathetic arousal"),
    "ACC":  SignalSpec("Accelerometer", "g", 32.0, -2, 2, "up",
                       "3-axis wrist movement acceleration"),
    "IBI":  SignalSpec("Inter-Beat Interval", "s", 0.0, 0.35, 1.2, "down",
                       "Time between consecutive heartbeats — HRV source"),
    "ECG":  SignalSpec("Electrocardiogram", "mV", 256.0, -2, 2, "up",
                       "Raw ECG signal"),
    "EEG":  SignalSpec("Electroencephalogram", "µV", 256.0, -100, 100, "up",
                       "Raw EEG brain activity"),
    "EMG":  SignalSpec("Electromyogram", "mV", 2000.0, -5, 5, "up",
                       "Muscle electrical activity"),
    "PPG":  SignalSpec("Photoplethysmography", "raw", 64.0, -500, 500, "up",
                       "Optical pulse signal"),
}

# Synonym → canonical key
SIGNAL_SYNONYMS: Dict[str, str] = {
    "hr": "HR", "heart_rate": "HR", "heartrate": "HR", "bpm": "HR",
    "pulse": "HR", "heart rate": "HR",
    "eda": "EDA", "gsr": "EDA", "skin_conductance": "EDA",
    "electrodermal": "EDA", "galvanic": "EDA",
    "bvp": "BVP", "blood_volume_pulse": "BVP", "ppg": "PPG",
    "temp": "TEMP", "temperature": "TEMP", "skin_temp": "TEMP",
    "body_temperature": "TEMP",
    "acc": "ACC", "accelerometer": "ACC", "accel": "ACC",
    "motion": "ACC", "x": "ACC", "y": "ACC", "z": "ACC",
    "ibi": "IBI", "rr_interval": "IBI", "nn_interval": "IBI",
    "inter_beat": "IBI",
    "ecg": "ECG", "eeg": "EEG", "emg": "EMG",
}

_FILENAME_SIGNAL_MAP = {
    "hr": "HR", "eda": "EDA", "bvp": "BVP", "temp": "TEMP",
    "acc": "ACC", "ibi": "IBI", "ecg": "ECG", "eeg": "EEG",
    "emg": "EMG", "ppg": "PPG",
}

# Physiological stress level labels (never clinical)
STRESS_LABELS = {
    (0.00, 0.25): ("Low",      "Low physiological stress proxy signal"),
    (0.25, 0.50): ("Moderate", "Moderate physiological stress proxy signal"),
    (0.50, 0.75): ("Elevated", "Elevated physiological stress proxy signal"),
    (0.75, 1.01): ("Critical", "Critical physiological stress proxy signal"),
}

DISCLAIMER = (
    "⚕️ Non-clinical: These scores are physiological proxy signals derived from "
    "wearable sensor data. They do not constitute medical diagnosis, burnout diagnosis, "
    "or clinical assessment. Consult a qualified professional for medical interpretation."
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WindowFeatures:
    window_id: int
    sample_start: int
    sample_end: int
    mean: float
    std: float
    min_val: float
    max_val: float
    median: float
    range_val: float
    iqr: float
    slope: float
    skewness: float
    kurtosis: float
    rolling_mean_first_half: float
    rolling_mean_last_half: float
    trend_diff: float
    n_peaks: int
    volatility: float
    signal_quality: float
    pct_25: float
    pct_75: float
    # Composite scores (0–1)
    stress_signal_score: float
    fatigue_signal_score: float
    physiological_instability: float
    signal_volatility_score: float
    anomaly_risk_score: float
    biosignal_confidence: float
    # Signal-specific features
    extra: Dict[str, float] = field(default_factory=dict)


@dataclass
class BiosignalProfile:
    # Identity
    signal_type: str          # "HR", "EDA", etc.
    canonical_name: str
    unit: str
    dataset_type: str = "biosignal_timeseries"
    row_unit: str     = "signal_samples"       # NEVER "employees"

    # Volume
    n_samples: int = 0
    n_windows: int = 0
    duration_seconds: float = 0.0
    estimated_fs: float = 0.0

    # Global statistics
    global_mean: float = 0.0
    global_std: float  = 0.0
    global_min: float  = 0.0
    global_max: float  = 0.0
    global_median: float = 0.0
    global_range: float  = 0.0

    # Composite scores (0–1)
    stress_signal_score: float = 0.0
    fatigue_signal_score: float = 0.0
    physiological_instability: float = 0.0
    signal_volatility_score: float = 0.0
    anomaly_risk_score: float = 0.0
    biosignal_confidence: float = 0.0

    # Early warning
    stress_level_label: str = "Low"
    stress_level_description: str = ""
    early_warning_status: str = "Normal"

    # Quality
    quality_score: float = 0.0
    flatline_detected: bool = False
    missing_rate: float = 0.0
    anomaly_count: int = 0

    # Windows
    window_features_df: Optional[pd.DataFrame] = None

    # Metadata
    warnings: List[str] = field(default_factory=list)
    global_stats: Dict[str, float] = field(default_factory=dict)
    spec: Optional[SignalSpec] = None

    # Non-clinical disclaimer (always attached)
    disclaimer: str = DISCLAIMER


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_signal_type(df: pd.DataFrame, filename: str = "") -> str:
    stem = filename.lower().replace(".csv", "").replace(".txt", "").replace(".dat", "").strip()
    if stem in _FILENAME_SIGNAL_MAP:
        return _FILENAME_SIGNAL_MAP[stem]
    for col in df.columns:
        cl = col.lower().strip().replace(" ", "_")
        if cl in SIGNAL_SYNONYMS:
            return SIGNAL_SYNONYMS[cl]
        for syn, canon in SIGNAL_SYNONYMS.items():
            if syn in cl:
                return canon
    return "unknown"


def _get_primary_series(df: pd.DataFrame, signal_type: str) -> pd.Series:
    """Extract primary numeric column."""
    spec = SIGNAL_REGISTRY.get(signal_type)
    for col in df.columns:
        cl = col.lower().strip().replace(" ", "_")
        if cl == signal_type.lower():
            return df[col].rename(signal_type)
        if spec:
            for syn, canon in SIGNAL_SYNONYMS.items():
                if canon == signal_type and syn in cl:
                    return df[col].rename(signal_type)
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) > 0:
        return df[num_cols[0]].rename(signal_type)
    raise ValueError(f"No numeric column found for signal type '{signal_type}'")


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLING FREQUENCY ESTIMATION
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_fs(df: pd.DataFrame, spec: Optional[SignalSpec]) -> float:
    for col in df.columns:
        cl = col.lower()
        if any(kw in cl for kw in ["time", "timestamp", "t", "sec"]):
            t = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(t) > 2:
                dt = float(np.median(np.diff(t.values[:500])))
                if 0 < dt < 10:
                    return round(1.0 / dt, 2)
    return spec.typical_fs if spec else 0.0


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL QUALITY
# ─────────────────────────────────────────────────────────────────────────────

def _signal_quality(series: pd.Series, spec: Optional[SignalSpec]) -> Tuple[float, bool]:
    s = series.dropna()
    if len(s) == 0:
        return 0.0, False
    score = 100.0
    flatline = s.std() < 1e-6
    if flatline:
        return 10.0, True
    miss = series.isna().mean()
    score -= miss * 50
    if spec:
        lo, hi = spec.normal_low, spec.normal_high
        # Allow 2× range for anomaly tolerance
        out = float(((s < lo * 0.5) | (s > hi * 2.0)).mean())
        score -= out * 30
    # Extreme spikes
    z = np.abs((s - s.mean()) / (s.std() + 1e-9))
    pct_extreme = float((z > 8).mean())
    score -= pct_extreme * 20
    return float(np.clip(score, 0, 100)), False


# ─────────────────────────────────────────────────────────────────────────────
# WINDOW FEATURE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _compute_slope(window: np.ndarray) -> float:
    if len(window) < 2:
        return 0.0
    x = np.arange(len(window), dtype=float)
    try:
        slope, *_ = np.polyfit(x, window, 1)
        return float(slope)
    except Exception:
        return 0.0


def _count_peaks(window: np.ndarray) -> int:
    if not _HAS_SCIPY or len(window) < 4:
        return 0
    try:
        height_thresh = np.mean(window)
        peaks, _ = sp_signal.find_peaks(window, height=height_thresh, distance=3)
        return int(len(peaks))
    except Exception:
        return 0


def _extract_window_features(window: np.ndarray, win_id: int,
                               start: int, end: int,
                               signal_type: str,
                               spec: Optional[SignalSpec]) -> WindowFeatures:
    n = len(window)
    hw = max(1, n // 2)
    diffs = np.abs(np.diff(window)) if n > 1 else np.array([0.0])

    mean_v   = float(np.mean(window))
    std_v    = float(np.std(window))
    slope_v  = _compute_slope(window)
    n_peaks  = _count_peaks(window)
    volatility = float(np.std(diffs))

    # Quality for this window
    q_score = 100.0
    if std_v < 1e-6:
        q_score = 10.0  # flatline window
    elif spec:
        out = float(np.mean((window < spec.normal_low * 0.5) |
                            (window > spec.normal_high * 2.0)))
        q_score -= out * 40

    # Signal-specific extras
    extra: Dict[str, float] = {}

    if signal_type == "HR":
        extra["heart_rate_mean"]       = round(mean_v, 2)
        extra["heart_rate_std"]        = round(std_v, 2)
        extra["heart_rate_volatility"] = round(volatility, 4)
        extra["elevated_hr_ratio"]     = float(np.mean(window > 90))
        extra["low_hr_ratio"]          = float(np.mean(window < 60))
        extra["fatigue_proxy"]         = round(float(np.mean(window < 65)), 4)
        # HR stress proxy: normalise elevation above resting 60 bpm
        extra["hr_stress_proxy"]       = float(np.clip((mean_v - 60) / 50.0, 0, 1))

    elif signal_type == "EDA":
        extra["eda_mean"] = round(mean_v, 4)
        extra["eda_std"]  = round(std_v, 4)
        spk = _count_peaks(window)
        extra["eda_spike_count"]            = float(spk)
        extra["stress_activation_score"]    = float(np.clip(spk / 8.0, 0, 1))
        extra["sympathetic_arousal_proxy"]  = float(np.clip(mean_v / 15.0, 0, 1))

    elif signal_type == "BVP":
        extra["bvp_mean"]                          = round(mean_v, 2)
        extra["bvp_std"]                           = round(std_v, 2)
        extra["bvp_volatility"]                    = round(volatility, 4)
        extra["cardiovascular_signal_instability"] = round(float(np.clip(volatility / 50.0, 0, 1)), 4)

    elif signal_type == "TEMP":
        extra["temp_mean"]         = round(mean_v, 2)
        extra["temp_std"]          = round(std_v, 4)
        extra["thermal_variability"] = round(volatility, 4)
        # Low temperature → sympathetic arousal → stress signal (inverted)
        extra["temp_stress_proxy"] = float(np.clip((37.0 - mean_v) / 7.0, 0, 1))

    elif signal_type == "ACC":
        mag = np.sqrt(np.sum(window ** 2)) if n > 0 else 0.0
        extra["movement_intensity"]   = round(float(np.clip(std_v / 2.0, 0, 1)), 4)
        extra["movement_variability"] = round(volatility / 2.0, 4)
        extra["inactivity_ratio"]     = float(np.mean(np.abs(window) < 0.1))

    elif signal_type == "IBI":
        # SDNN, RMSSD
        if n > 1:
            extra["hrv_sdnn_ms"]  = round(float(std_v * 1000), 2)
            extra["hrv_rmssd_ms"] = round(float(np.sqrt(np.mean(np.diff(window) ** 2))) * 1000, 2)
            extra["ibi_mean_ms"]  = round(mean_v * 1000, 2)
            sdnn_norm = float(np.clip(extra["hrv_sdnn_ms"] / 100.0, 0, 1))
            extra["hrv_stress_proxy"] = round(1 - sdnn_norm, 4)  # low HRV = high stress

    # ── Composite scores ─────────────────────────────────────────────────────
    stress = 0.0
    fatigue = 0.0
    instab = 0.0

    if signal_type == "HR":
        stress  = extra.get("hr_stress_proxy", 0.0)
        fatigue = extra.get("fatigue_proxy", 0.0)
        instab  = float(np.clip(volatility / 10.0, 0, 1))

    elif signal_type == "EDA":
        stress = extra.get("stress_activation_score", 0.0) * 0.6 + \
                 extra.get("sympathetic_arousal_proxy", 0.0) * 0.4
        instab = float(np.clip(std_v / 5.0, 0, 1))

    elif signal_type == "BVP":
        stress = extra.get("cardiovascular_signal_instability", 0.0) * 0.5
        instab = extra.get("cardiovascular_signal_instability", 0.0)

    elif signal_type == "TEMP":
        stress = extra.get("temp_stress_proxy", 0.0)

    elif signal_type == "IBI":
        stress  = extra.get("hrv_stress_proxy", 0.0)
        fatigue = extra.get("hrv_stress_proxy", 0.0) * 0.7
        instab  = float(np.clip(volatility / 0.1, 0, 1))

    volatility_score = float(np.clip(volatility / (np.mean(np.abs(window)) + 1e-9), 0, 1))
    # z-score anomaly count for this window
    z = np.abs((window - mean_v) / (std_v + 1e-9))
    anomaly_risk = float(np.clip((z > 2.5).mean() * 3, 0, 1))

    return WindowFeatures(
        window_id             = win_id,
        sample_start          = start,
        sample_end            = end,
        mean                  = round(mean_v, 4),
        std                   = round(std_v, 4),
        min_val               = round(float(np.min(window)), 4),
        max_val               = round(float(np.max(window)), 4),
        median                = round(float(np.median(window)), 4),
        range_val             = round(float(np.max(window) - np.min(window)), 4),
        iqr                   = round(float(np.percentile(window, 75) - np.percentile(window, 25)), 4),
        slope                 = round(slope_v, 6),
        skewness              = round(float(pd.Series(window).skew()), 4),
        kurtosis              = round(float(pd.Series(window).kurtosis()), 4),
        rolling_mean_first_half = round(float(np.mean(window[:hw])), 4),
        rolling_mean_last_half  = round(float(np.mean(window[hw:])), 4),
        trend_diff            = round(float(np.mean(window[hw:])) - float(np.mean(window[:hw])), 4),
        n_peaks               = n_peaks,
        volatility            = round(volatility, 4),
        signal_quality        = round(float(np.clip(q_score, 0, 100)), 1),
        pct_25                = round(float(np.percentile(window, 25)), 4),
        pct_75                = round(float(np.percentile(window, 75)), 4),
        stress_signal_score   = round(float(np.clip(stress, 0, 1)), 4),
        fatigue_signal_score  = round(float(np.clip(fatigue, 0, 1)), 4),
        physiological_instability = round(float(np.clip(instab, 0, 1)), 4),
        signal_volatility_score   = round(float(np.clip(volatility_score, 0, 1)), 4),
        anomaly_risk_score        = round(anomaly_risk, 4),
        biosignal_confidence      = round(float(np.clip(q_score / 100.0, 0, 1)), 4),
        extra                 = {k: round(v, 4) for k, v in extra.items()},
    )


def _windows_to_dataframe(features: List[WindowFeatures]) -> pd.DataFrame:
    rows = []
    for f in features:
        row = {
            "WindowID": f.window_id,
            "SampleStart": f.sample_start,
            "SampleEnd": f.sample_end,
            "Mean": f.mean, "Std": f.std,
            "Min": f.min_val, "Max": f.max_val,
            "Median": f.median, "Range": f.range_val, "IQR": f.iqr,
            "Slope": f.slope,
            "Skewness": f.skewness, "Kurtosis": f.kurtosis,
            "RollingMeanFirst": f.rolling_mean_first_half,
            "RollingMeanLast": f.rolling_mean_last_half,
            "TrendDiff": f.trend_diff,
            "NPeaks": f.n_peaks, "Volatility": f.volatility,
            "SignalQuality": f.signal_quality,
            "Pct25": f.pct_25, "Pct75": f.pct_75,
            "StressSignalScore": f.stress_signal_score,
            "FatigueSignalScore": f.fatigue_signal_score,
            "PhysiologicalInstability": f.physiological_instability,
            "SignalVolatilityScore": f.signal_volatility_score,
            "AnomalyRiskScore": f.anomaly_risk_score,
            "BiosignalConfidence": f.biosignal_confidence,
        }
        row.update(f.extra)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["DatasetType"] = "biosignal_timeseries"
    df["RowUnit"]     = "time_windows"  # explicitly NOT "employees"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STRESS LEVEL LABEL
# ─────────────────────────────────────────────────────────────────────────────

def _stress_label(score: float) -> Tuple[str, str]:
    for (lo, hi), (level, desc) in STRESS_LABELS.items():
        if lo <= score < hi:
            return level, desc
    return "Low", "Low physiological stress proxy signal"


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL STATS
# ─────────────────────────────────────────────────────────────────────────────

def _global_stats(series: pd.Series, spec: Optional[SignalSpec]) -> Dict[str, float]:
    s = series.dropna()
    stats = {
        "mean": float(s.mean()),
        "std":  float(s.std()),
        "min":  float(s.min()),
        "max":  float(s.max()),
        "median": float(s.median()),
        "range":  float(s.max() - s.min()),
        "iqr":    float(s.quantile(0.75) - s.quantile(0.25)),
        "skew":   float(s.skew()),
        "cv":     float(s.std() / abs(s.mean())) if s.mean() != 0 else 0.0,
    }
    if spec:
        stats["pct_above_normal"] = float((s > spec.normal_high).mean())
        stats["pct_below_normal"] = float((s < spec.normal_low).mean())
    return {k: round(v, 4) for k, v in stats.items()}


# ─────────────────────────────────────────────────────────────────────────────
# ANOMALY COUNT
# ─────────────────────────────────────────────────────────────────────────────

def _count_anomalies(series: pd.Series, threshold: float = 2.8) -> int:
    s = series.dropna()
    if len(s) < 10 or s.std() < 1e-9:
        return 0
    z = np.abs((s - s.mean()) / s.std())
    return int((z > threshold).sum())


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ADAPTER
# ─────────────────────────────────────────────────────────────────────────────

class BiosignalAdapter:
    """
    Analyses any physiological sensor CSV and returns a BiosignalProfile.
    All outputs use signal-domain language (samples, windows) — NEVER employee language.

    Usage
    -----
    adapter = BiosignalAdapter()
    profile = adapter.analyse(df, signal_type="HR", filename="HR.csv")
    """

    DEFAULT_WINDOW_SECS  = 30    # 30-second windows by default
    DEFAULT_WINDOW_SAMPS = 60    # fallback if fs unknown
    DEFAULT_STEP_FRAC    = 0.5   # 50% overlap

    def analyse(self,
                df: pd.DataFrame,
                signal_type: Optional[str] = None,
                filename: str = "",
                window_size: Optional[int] = None,
                step_size: Optional[int] = None) -> BiosignalProfile:

        if signal_type is None or signal_type == "unknown":
            signal_type = detect_signal_type(df, filename)
            if not signal_type:
                signal_type = "unknown"

        spec   = SIGNAL_REGISTRY.get(signal_type)
        series = _get_primary_series(df, signal_type)
        series = pd.to_numeric(series, errors="coerce")

        n_total   = len(series)
        n_samples = int(series.notna().sum())
        miss_rate = float(series.isna().mean())

        fs = _estimate_fs(df, spec)
        duration = n_samples / max(fs, 1) if fs > 0 else 0.0

        q_score, is_flatline = _signal_quality(series, spec)
        g_stats = _global_stats(series, spec)
        n_anomalies = _count_anomalies(series)

        # Window sizing
        if window_size:
            ws = window_size
        elif fs > 0:
            ws = int(self.DEFAULT_WINDOW_SECS * fs)
        else:
            ws = self.DEFAULT_WINDOW_SAMPS
        ws = max(10, min(ws, min(n_samples, 5000)))
        ss = step_size or max(1, int(ws * self.DEFAULT_STEP_FRAC))

        # Extract windows
        values = series.dropna().values
        feature_list: List[WindowFeatures] = []
        for i, start in enumerate(range(0, len(values) - ws + 1, ss)):
            end = start + ws
            wf  = _extract_window_features(
                values[start:end], i, start, end, signal_type, spec,
            )
            feature_list.append(wf)

        win_df = _windows_to_dataframe(feature_list) if feature_list else None

        # Global composite scores (mean across windows)
        if feature_list:
            stress  = float(np.mean([f.stress_signal_score for f in feature_list]))
            fatigue = float(np.mean([f.fatigue_signal_score for f in feature_list]))
            instab  = float(np.mean([f.physiological_instability for f in feature_list]))
            vol     = float(np.mean([f.signal_volatility_score for f in feature_list]))
            anom_r  = float(np.mean([f.anomaly_risk_score for f in feature_list]))
            bconf   = float(np.mean([f.biosignal_confidence for f in feature_list]))
        else:
            # Fallback global scores from raw signal
            stress = fatigue = instab = vol = anom_r = 0.0
            bconf  = q_score / 100.0
            if spec and n_samples > 0:
                s = series.dropna()
                if spec.stress_direction == "up":
                    stress = float(np.clip((s.mean() - spec.normal_high * 0.85) /
                                           (spec.normal_high * 0.5), 0, 1))
                else:
                    stress = float(np.clip((spec.normal_low * 1.15 - s.mean()) /
                                           (spec.normal_low * 0.5), 0, 1))

        stress_label, stress_desc = _stress_label(stress)

        # Early warning
        if stress >= 0.75:
            ew_status = "Critical"
        elif stress >= 0.50:
            ew_status = "Elevated"
        elif stress >= 0.25:
            ew_status = "Watchlist"
        else:
            ew_status = "Normal"

        # Warnings
        warnings: List[str] = []
        if is_flatline:
            warnings.append("Flatline detected — check sensor contact and data quality")
        if miss_rate > 0.20:
            warnings.append(f"High missing rate: {miss_rate:.0%} of samples missing")
        if n_samples < 100:
            warnings.append(f"Short signal: only {n_samples} samples — window analysis may be unreliable")
        if q_score < 50:
            warnings.append(f"Low signal quality ({q_score:.0f}/100) — interpret results cautiously")
        if not feature_list:
            warnings.append("No windows could be extracted — signal too short")

        return BiosignalProfile(
            signal_type              = signal_type,
            canonical_name           = spec.canonical if spec else signal_type,
            unit                     = spec.unit if spec else "raw",
            dataset_type             = "biosignal_timeseries",
            row_unit                 = "signal_samples",   # NEVER "employees"
            n_samples                = n_samples,
            n_windows                = len(feature_list),
            duration_seconds         = round(duration, 2),
            estimated_fs             = round(fs, 2),
            global_mean              = round(float(g_stats.get("mean", 0)), 4),
            global_std               = round(float(g_stats.get("std", 0)), 4),
            global_min               = round(float(g_stats.get("min", 0)), 4),
            global_max               = round(float(g_stats.get("max", 0)), 4),
            global_median            = round(float(g_stats.get("median", 0)), 4),
            global_range             = round(float(g_stats.get("range", 0)), 4),
            stress_signal_score      = round(stress, 4),
            fatigue_signal_score     = round(fatigue, 4),
            physiological_instability= round(instab, 4),
            signal_volatility_score  = round(vol, 4),
            anomaly_risk_score       = round(anom_r, 4),
            biosignal_confidence     = round(bconf, 4),
            stress_level_label       = stress_label,
            stress_level_description = stress_desc,
            early_warning_status     = ew_status,
            quality_score            = round(q_score, 1),
            flatline_detected        = is_flatline,
            missing_rate             = round(miss_rate, 4),
            anomaly_count            = n_anomalies,
            window_features_df       = win_df,
            warnings                 = warnings,
            global_stats             = g_stats,
            spec                     = spec,
            disclaimer               = DISCLAIMER,
        )

    def multi_signal_analysis(self,
                               signal_dfs: Dict[str, pd.DataFrame],
                               filename_map: Optional[Dict[str, str]] = None) -> Dict[str, BiosignalProfile]:
        filename_map = filename_map or {}
        return {
            sig: self.analyse(df, signal_type=sig,
                              filename=filename_map.get(sig, f"{sig}.csv"))
            for sig, df in signal_dfs.items()
        }

    def combined_risk_summary(self,
                               profiles: Dict[str, BiosignalProfile]) -> Dict[str, Any]:
        stress_vals  = [p.stress_signal_score for p in profiles.values()]
        quality_vals = [p.quality_score for p in profiles.values()]
        return {
            "composite_stress_score":  round(float(np.mean(stress_vals)) if stress_vals else 0.0, 4),
            "signal_quality_mean":     round(float(np.mean(quality_vals)) if quality_vals else 0.0, 2),
            "n_signals_analysed":      len(profiles),
            "high_stress_signals":     sum(1 for p in profiles.values()
                                           if p.stress_signal_score > 0.65),
            "row_unit":                "signal_samples",  # explicitly NOT employees
            "disclaimer":              DISCLAIMER,
        }
