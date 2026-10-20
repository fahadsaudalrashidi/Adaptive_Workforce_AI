"""
Time-Series Engine — Autonomous Temporal Intelligence

Handles any time-indexed dataset for:
  - Trend detection and slope analysis
  - Anomaly detection (z-score + IQR)
  - Bootstrap confidence bands
  - Risk escalation scoring
  - Short-term forecasting (linear + exponential smoothing + Prophet if available)
  - Early warning classification: Stable / Watchlist / Elevated / Critical
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
    _HAS_PROPHET = True
except ImportError:
    _HAS_PROPHET = False

from config.settings import (
    TS_MIN_PERIODS, TS_FORECAST_HORIZONS,
    TS_BOOTSTRAP_N, TS_ANOMALY_ZSCORE, TS_SEASONAL_PERIODS,
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TrendResult:
    metric: str
    slope: float
    intercept: float
    r_squared: float
    p_value: float
    direction: str          # "increasing" / "decreasing" / "stable"
    magnitude: str          # "strong" / "moderate" / "weak"
    periods: int


@dataclass
class AnomalyEvent:
    period: Any             # index value (date, integer, etc.)
    metric: str
    value: float
    z_score: float
    severity: str           # "Critical" / "Elevated"
    direction: str          # "spike" / "dip"


@dataclass
class ForecastResult:
    metric: str
    method: str             # "linear" / "exp_smoothing" / "prophet"
    horizon: int
    projected: float
    lower_95: float
    upper_95: float
    band_width: float
    trend_direction: str
    confidence: float       # 0–1


@dataclass
class EscalationResult:
    level: str              # Stable / Watchlist / Elevated / Critical
    score: float            # 0–100
    drivers: List[str]      # contributing factors
    recommended_action: str


@dataclass
class TSAnalysisResult:
    metric_col: str
    time_col: Optional[str]
    n_periods: int
    time_resolution: Optional[str]
    trends: Dict[str, TrendResult] = field(default_factory=dict)
    anomalies: List[AnomalyEvent] = field(default_factory=list)
    forecasts: Dict[int, ForecastResult] = field(default_factory=dict)
    escalation: Optional[EscalationResult] = None
    synthetic_mode: bool = False
    warnings: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC TIMELINE (for HR datasets without dates)
# ─────────────────────────────────────────────────────────────────────────────

def build_synthetic_timeline(df: pd.DataFrame,
                               risk_col: str,
                               tenure_col: Optional[str] = None,
                               reference_year: int = 2024,
                               n_buckets: int = 8) -> Optional[pd.DataFrame]:
    """
    When no real date column is present, create a pseudo-time-series by
    binning employees into tenure cohorts and computing mean risk per cohort.
    Returns a DataFrame with columns [period, <risk_col>_mean] or None.
    """
    if risk_col not in df.columns:
        return None

    # Find a usable tenure column
    tenure = None
    candidates = [tenure_col] if tenure_col else []
    candidates += [c for c in df.columns if any(kw in c.lower()
                   for kw in ["tenure", "years_at", "service", "yearsatcompany"])]

    for cand in candidates:
        if cand and cand in df.columns:
            series = pd.to_numeric(df[cand], errors="coerce").dropna()
            if len(series) > 5:
                tenure = series
                break

    if tenure is None:
        logger.debug("No tenure column found for synthetic timeline")
        return None

    risk_series = pd.to_numeric(df[risk_col], errors="coerce")
    combined    = pd.DataFrame({"tenure": tenure, "risk": risk_series}).dropna()
    if len(combined) < n_buckets * 2:
        return None

    combined["tenure_bucket"] = pd.qcut(combined["tenure"], q=n_buckets, duplicates="drop")
    agg = (combined.groupby("tenure_bucket")["risk"]
           .agg(mean="mean", std="std", count="count")
           .reset_index())

    # Convert buckets to approximate month offsets
    base = pd.Timestamp(f"{reference_year}-01-01")
    agg["period"] = [base + pd.DateOffset(months=i * 3) for i in range(len(agg))]
    agg.rename(columns={"mean": f"{risk_col}_mean"}, inplace=True)
    return agg[["period", f"{risk_col}_mean", "std", "count"]]


# ─────────────────────────────────────────────────────────────────────────────
# TREND DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_trend(series: pd.Series, metric_name: str = "metric") -> TrendResult:
    s = pd.to_numeric(series, errors="coerce").dropna()
    n = len(s)
    if n < TS_MIN_PERIODS:
        return TrendResult(metric=metric_name, slope=0, intercept=float(s.mean()),
                            r_squared=0, p_value=1.0,
                            direction="stable", magnitude="weak", periods=n)

    x = np.arange(n, dtype=float)
    slope, intercept, r_val, p_val, _ = sp_stats.linregress(x, s.values)

    r2    = r_val ** 2
    total_change = abs(slope * n)
    rel_change   = total_change / (abs(s.mean()) + 1e-9)

    if p_val > 0.10 or rel_change < 0.05:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    if rel_change > 0.30:
        magnitude = "strong"
    elif rel_change > 0.10:
        magnitude = "moderate"
    else:
        magnitude = "weak"

    return TrendResult(
        metric     = metric_name,
        slope      = round(float(slope), 6),
        intercept  = round(float(intercept), 4),
        r_squared  = round(r2, 4),
        p_value    = round(float(p_val), 4),
        direction  = direction,
        magnitude  = magnitude,
        periods    = n,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ANOMALY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_anomalies(series: pd.Series,
                      time_index: Optional[pd.Series] = None,
                      metric_name: str = "metric",
                      zscore_threshold: float = TS_ANOMALY_ZSCORE) -> List[AnomalyEvent]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 5:
        return []

    mu, sigma = s.mean(), s.std()
    if sigma < 1e-9:
        return []

    zscores = (s - mu) / sigma
    events: List[AnomalyEvent] = []

    for idx, (z, val) in enumerate(zip(zscores, s)):
        if abs(z) >= zscore_threshold:
            period = time_index.iloc[idx] if (time_index is not None
                                               and idx < len(time_index)) else idx
            events.append(AnomalyEvent(
                period    = period,
                metric    = metric_name,
                value     = round(float(val), 4),
                z_score   = round(float(z), 3),
                severity  = "Critical" if abs(z) >= zscore_threshold * 1.5 else "Elevated",
                direction = "spike" if z > 0 else "dip",
            ))

    return sorted(events, key=lambda e: abs(e.z_score), reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# BOOTSTRAP CONFIDENCE BANDS
# ─────────────────────────────────────────────────────────────────────────────

def forecast_with_bands(series: pd.Series,
                         horizon: int,
                         method: str = "linear",
                         n_boot: int = TS_BOOTSTRAP_N,
                         metric_name: str = "metric") -> ForecastResult:
    s = pd.to_numeric(series, errors="coerce").dropna().values
    n = len(s)
    if n < TS_MIN_PERIODS:
        last = float(s[-1]) if n > 0 else 0.0
        return ForecastResult(
            metric=metric_name, method="fallback", horizon=horizon,
            projected=last, lower_95=last*0.8, upper_95=last*1.2,
            band_width=last*0.4, trend_direction="stable", confidence=0.3,
        )

    x = np.arange(n, dtype=float)
    x_pred = float(n + horizon)

    boot_preds: List[float] = []
    rs = np.random.RandomState(42)
    for _ in range(n_boot):
        idx = rs.choice(n, size=n, replace=True)
        xs, ys = x[idx], s[idx]
        try:
            if method == "linear":
                slp, icpt, *_ = sp_stats.linregress(xs, ys)
                pred = slp * x_pred + icpt
            else:  # exp smoothing fallback
                alpha = 0.3
                sm = ys[0]
                for v in ys[1:]:
                    sm = alpha * v + (1 - alpha) * sm
                trend = (ys[-1] - ys[0]) / max(n - 1, 1)
                pred  = sm + trend * horizon
            boot_preds.append(float(pred))
        except Exception:
            pass

    if not boot_preds:
        boot_preds = [float(s[-1])]

    arr  = np.array(boot_preds)
    proj = float(np.mean(arr))
    lo   = float(np.percentile(arr, 2.5))
    hi   = float(np.percentile(arr, 97.5))

    trend_result = detect_trend(pd.Series(s), metric_name)
    confidence   = min(0.95, max(0.3, trend_result.r_squared))

    return ForecastResult(
        metric         = metric_name,
        method         = method,
        horizon        = horizon,
        projected      = round(proj, 4),
        lower_95       = round(lo, 4),
        upper_95       = round(hi, 4),
        band_width     = round(hi - lo, 4),
        trend_direction = trend_result.direction,
        confidence     = round(confidence, 4),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PROPHET FORECASTING
# ─────────────────────────────────────────────────────────────────────────────

def prophet_forecast(series: pd.Series,
                      time_index: pd.Series,
                      horizon: int = 12,
                      metric_name: str = "metric") -> Optional[ForecastResult]:
    if not _HAS_PROPHET:
        return None
    try:
        df_p = pd.DataFrame({
            "ds": pd.to_datetime(time_index, errors="coerce"),
            "y":  pd.to_numeric(series, errors="coerce"),
        }).dropna()
        if len(df_p) < TS_MIN_PERIODS:
            return None

        m = Prophet(yearly_seasonality=False, weekly_seasonality=False,
                    daily_seasonality=False, interval_width=0.95, verbose=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(df_p)

        last_date = df_p["ds"].max()
        future_dates = [last_date + pd.DateOffset(months=i+1) for i in range(horizon)]
        future = pd.DataFrame({"ds": future_dates})
        fc = m.predict(future)

        last = fc.tail(1).iloc[0]
        return ForecastResult(
            metric         = metric_name,
            method         = "prophet",
            horizon        = horizon,
            projected      = round(float(last["yhat"]), 4),
            lower_95       = round(float(last["yhat_lower"]), 4),
            upper_95       = round(float(last["yhat_upper"]), 4),
            band_width     = round(float(last["yhat_upper"] - last["yhat_lower"]), 4),
            trend_direction = "increasing" if float(last["yhat"]) > float(df_p["y"].mean()) else "decreasing",
            confidence     = 0.85,
        )
    except Exception as e:
        logger.debug("Prophet forecast failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# RISK ESCALATION SCORING
# ─────────────────────────────────────────────────────────────────────────────

_ESCALATION_THRESHOLDS = {"Critical": 70, "Elevated": 45, "Watchlist": 22}


def compute_risk_escalation(trend_data: Dict[str, Any],
                              anomalies: Optional[List[AnomalyEvent]] = None) -> EscalationResult:
    """
    Composite escalation score (0–100) from multiple risk signals.
    trend_data: dict of metric_name → recent values (list/array) or TrendResult
    """
    score = 0.0
    drivers: List[str] = []

    def _add(pts: float, reason: str):
        nonlocal score
        score += pts
        if pts > 0:
            drivers.append(reason)

    # Anomaly contribution
    if anomalies:
        n_crit = sum(1 for a in anomalies if a.severity == "Critical")
        n_elev = sum(1 for a in anomalies if a.severity == "Elevated")
        _add(min(20, n_crit * 8 + n_elev * 3), f"{len(anomalies)} anomalies detected")

    # Trend contribution
    for metric, data in trend_data.items():
        if isinstance(data, TrendResult):
            tr = data
        elif isinstance(data, (list, np.ndarray, pd.Series)):
            tr = detect_trend(pd.Series(data), metric)
        else:
            continue

        if tr.direction == "increasing" and any(k in metric.lower()
                for k in ["risk", "burnout", "attrition", "stress", "absence"]):
            pts = {"strong": 15, "moderate": 8, "weak": 3}.get(tr.magnitude, 0)
            _add(pts, f"{metric} trending up ({tr.magnitude})")
        elif tr.direction == "decreasing" and any(k in metric.lower()
                for k in ["engagement", "satisfaction", "performance"]):
            pts = {"strong": 15, "moderate": 8, "weak": 3}.get(tr.magnitude, 0)
            _add(pts, f"{metric} declining ({tr.magnitude})")

    score = min(100, max(0, score))

    if score >= _ESCALATION_THRESHOLDS["Critical"]:
        level  = "Critical"
        action = "Immediate executive intervention required"
    elif score >= _ESCALATION_THRESHOLDS["Elevated"]:
        level  = "Elevated"
        action = "Manager escalation and targeted retention actions needed"
    elif score >= _ESCALATION_THRESHOLDS["Watchlist"]:
        level  = "Watchlist"
        action = "Monitor closely; schedule departmental pulse check"
    else:
        level  = "Stable"
        action = "Continue standard monitoring; review in next cycle"

    return EscalationResult(
        level               = level,
        score               = round(score, 1),
        drivers             = drivers,
        recommended_action  = action,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class TimeSeriesEngine:
    """
    Full autonomous time-series analysis pipeline.

    Usage
    -----
    engine = TimeSeriesEngine()
    result = engine.analyse(df, metric_col="attrition_rate",
                             time_col="month", horizons=[3, 6, 12])
    """

    def analyse(self,
                df: pd.DataFrame,
                metric_col: str,
                time_col: Optional[str] = None,
                horizons: Optional[List[int]] = None,
                synthetic_fallback: bool = True) -> TSAnalysisResult:

        horizons = horizons or TS_FORECAST_HORIZONS
        warnings_list: List[str] = []

        # Try real time series
        ts_df, synthetic = self._build_ts_df(
            df, metric_col, time_col, synthetic_fallback, warnings_list,
        )

        if ts_df is None or len(ts_df) < TS_MIN_PERIODS:
            warnings_list.append(f"Insufficient time-series data for '{metric_col}'")
            return TSAnalysisResult(
                metric_col     = metric_col,
                time_col       = time_col,
                n_periods      = 0,
                time_resolution = None,
                warnings       = warnings_list,
            )

        time_index = ts_df.index if time_col is None else ts_df.get(time_col)
        metric_series = ts_df[metric_col]

        # Trend
        trend = detect_trend(metric_series, metric_col)

        # Anomalies
        anomalies = detect_anomalies(metric_series, pd.Series(ts_df.index),
                                      metric_col)

        # Forecasts
        forecasts: Dict[int, ForecastResult] = {}
        for h in horizons:
            # Try Prophet first
            fc = None
            if time_col and time_col in ts_df.columns:
                fc = prophet_forecast(metric_series, ts_df[time_col], h, metric_col)
            if fc is None:
                fc = forecast_with_bands(metric_series, h, "linear",
                                          TS_BOOTSTRAP_N, metric_col)
            forecasts[h] = fc

        # Escalation
        escalation = compute_risk_escalation(
            {metric_col: trend},
            anomalies,
        )

        return TSAnalysisResult(
            metric_col      = metric_col,
            time_col        = time_col,
            n_periods       = len(ts_df),
            time_resolution = None,
            trends          = {metric_col: trend},
            anomalies       = anomalies[:10],
            forecasts       = forecasts,
            escalation      = escalation,
            synthetic_mode  = synthetic,
            warnings        = warnings_list,
        )

    def _build_ts_df(self,
                     df: pd.DataFrame,
                     metric_col: str,
                     time_col: Optional[str],
                     synthetic_fallback: bool,
                     warnings_list: List[str]) -> Tuple[Optional[pd.DataFrame], bool]:
        if metric_col not in df.columns:
            return None, False

        # Real time series
        if time_col and time_col in df.columns:
            ts = df[[time_col, metric_col]].copy()
            ts[time_col] = pd.to_datetime(ts[time_col], errors="coerce",
                                           infer_datetime_format=True)
            ts = ts.dropna().sort_values(time_col)
            ts[metric_col] = pd.to_numeric(ts[metric_col], errors="coerce")
            ts = ts.dropna(subset=[metric_col])
            if len(ts) >= TS_MIN_PERIODS:
                return ts.reset_index(drop=True), False

        # Synthetic fallback
        if synthetic_fallback:
            syn = build_synthetic_timeline(df, metric_col)
            if syn is not None and len(syn) >= TS_MIN_PERIODS:
                rename_col = f"{metric_col}_mean"
                if rename_col in syn.columns:
                    syn = syn.rename(columns={rename_col: metric_col})
                warnings_list.append("Using synthetic tenure-based timeline (no date column)")
                return syn.reset_index(drop=True), True

        return None, False
