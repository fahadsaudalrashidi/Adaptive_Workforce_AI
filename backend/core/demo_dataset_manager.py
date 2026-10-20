"""
Demo Dataset Manager — Phase 11.

Manages safe loading, switching, and isolation of demo datasets for the
enterprise demonstration workflow.

Provides three demo dataset modes:
  1. saudi_attrition  — 5 synthetic Saudi attrition datasets (from demo_company_generator)
  2. jadarat_market   — Synthetic job market posting dataset (market intelligence mode)
  3. governance_blocked — Dataset that triggers governance blocking (PII/leakage demo)

Design rules:
  - Demo data is ALWAYS marked DEMO_MODE=True
  - Demo data NEVER mixes with real uploaded data
  - Switching demo clears all state from previous demo
  - Attrition modeling is permitted only for saudi_attrition mode
  - Market intelligence is shown for jadarat_market mode
  - governance_blocked mode always returns BLOCKED readiness level
  - No external data loaded — all demo data is generated in-process
  - Thread-safe (singleton with lock)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from backend.core.demo_company_generator import DemoCompanyGenerator, _COMPANY_PROFILES

logger = logging.getLogger(__name__)


# ── Demo mode enum ────────────────────────────────────────────────────────────

class DemoMode(str, Enum):
    SAUDI_ATTRITION  = "saudi_attrition"
    JADARAT_MARKET   = "jadarat_market"
    GOVERNANCE_BLOCKED = "governance_blocked"
    NONE             = "none"


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class DemoDatasetResult:
    success: bool
    demo_mode: DemoMode
    company_id: Optional[str]          # None for market/blocked modes
    company_name_en: Optional[str]
    company_name_ar: Optional[str]
    dataset: Optional[pd.DataFrame]    # The demo DataFrame (always DEMO_MODE=True)
    row_count: int
    column_count: int
    analysis_mode: str                 # workforce_stability | market_intelligence | blocked
    attrition_modeling_allowed: bool
    readiness_level: str               # READY | CONDITIONAL | BLOCKED
    governance_notes: list[str]
    loaded_at: str
    error: Optional[str] = None


# ── Jadarat market demo ───────────────────────────────────────────────────────

def _generate_jadarat_demo(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic Jadarat-style job market posting dataset."""
    rng = np.random.default_rng(seed)
    regions = ["Riyadh", "Jeddah", "Dammam", "Makkah", "Madinah", "Tabuk", "Abha"]
    sectors = ["Technology", "Healthcare", "Finance", "Manufacturing", "Retail", "Education"]
    titles  = [
        "Software Engineer", "Data Analyst", "Project Manager", "HR Specialist",
        "Financial Analyst", "Operations Manager", "Marketing Coordinator",
        "Accountant", "IT Support", "Business Development Manager",
    ]
    contracts = ["Full-time", "Part-time", "Contract"]
    qualifs   = ["Bachelor's", "Diploma", "Master's", "High School"]

    rows = []
    for i in range(n):
        has_salary = rng.random() > 0.35
        rows.append({
            "job_title":    rng.choice(titles),
            "comp_name":    f"Company_{rng.integers(100, 999)}",  # anonymised
            "comp_type":    rng.choice(["Private", "Government", "Mixed"]),
            "comp_size":    rng.choice(["1-49", "50-199", "200-999", "1000+"]),
            "eco_activity": rng.choice(sectors),
            "qualif":       rng.choice(qualifs),
            "contract":     rng.choice(contracts),
            "positions":    f"0 / {rng.integers(1, 6)}",
            "exper":        f"{rng.choice([0, 1, 2, 3, 5])} Years",
            "region":       rng.choice(regions),
            "city":         rng.choice(["Riyadh", "Jeddah", "Dammam", "Khobar"]),
            "benefits":     (
                f"['Salary', '{rng.integers(5000, 20000)}.0']"
                if has_salary
                else "['Housing', 'Transportation']"
            ),
            "job_date":     f"{rng.integers(1, 28):02d}/{rng.integers(1, 12):02d}/144{rng.integers(0, 4)}",
            "gender":       rng.choice(["Male", "Female", "Both"]),
        })

    df = pd.DataFrame(rows)
    df.attrs["DEMO_MODE"] = True
    df.attrs["dataset_type"] = "JOB_MARKET_POSTING_DATASET"
    return df


# ── Governance-blocked demo ───────────────────────────────────────────────────

def _generate_governance_blocked_demo(n: int = 150, seed: int = 99) -> pd.DataFrame:
    """
    Generate a dataset that triggers governance blocking —
    useful for demonstrating PII detection and leakage prevention.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        rows.append({
            "employee_id":      f"EMP{i:04d}",
            "national_id":      f"10{rng.integers(10000000, 99999999)}",  # PII trigger
            "email":            f"emp{i}@company.sa",                      # PII trigger
            "job_satisfaction": rng.choice(["Satisfied", "Not Satisfied"]),
            "department":       rng.choice(["IT", "Finance", "HR"]),
            "resignation_date": "2024-01-15" if rng.random() > 0.8 else None,  # Leakage trigger
            "termination_date": "2024-02-01" if rng.random() > 0.9 else None,  # Leakage trigger
            "attrition":        rng.choice(["Yes", "No"]),
        })
    df = pd.DataFrame(rows)
    df.attrs["DEMO_MODE"] = True
    df.attrs["dataset_type"] = "BLOCKED_DEMO"
    return df


# ── Manager ───────────────────────────────────────────────────────────────────

class DemoDatasetManager:
    """
    Manages the lifecycle of demo datasets.

    Usage:
        mgr = DemoDatasetManager()
        result = mgr.load(DemoMode.SAUDI_ATTRITION, company_id="national-industrial-holdings")
        result = mgr.load(DemoMode.JADARAT_MARKET)
        result = mgr.load(DemoMode.GOVERNANCE_BLOCKED)
        mgr.reset()
    """

    _instance: Optional["DemoDatasetManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._generator = DemoCompanyGenerator()
        self._active_mode: DemoMode = DemoMode.NONE
        self._active_result: Optional[DemoDatasetResult] = None
        self._state_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "DemoDatasetManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(
        self,
        mode: DemoMode,
        company_id: Optional[str] = None,
    ) -> DemoDatasetResult:
        """
        Load a demo dataset for the specified mode.
        Clears any previously active demo state before loading.
        """
        self.reset()

        if mode == DemoMode.SAUDI_ATTRITION:
            result = self._load_attrition(company_id)
        elif mode == DemoMode.JADARAT_MARKET:
            result = self._load_jadarat()
        elif mode == DemoMode.GOVERNANCE_BLOCKED:
            result = self._load_blocked()
        else:
            result = DemoDatasetResult(
                success=False,
                demo_mode=mode,
                company_id=None,
                company_name_en=None,
                company_name_ar=None,
                dataset=None,
                row_count=0,
                column_count=0,
                analysis_mode="none",
                attrition_modeling_allowed=False,
                readiness_level="BLOCKED",
                governance_notes=["Demo mode NONE — no dataset loaded"],
                loaded_at=datetime.now(timezone.utc).isoformat(),
                error="No demo mode specified",
            )

        with self._state_lock:
            self._active_mode = mode
            self._active_result = result

        if result.success:
            logger.info(
                "Demo loaded: mode=%s company=%s rows=%d",
                mode, company_id, result.row_count,
            )
        else:
            logger.warning("Demo load failed: mode=%s error=%s", mode, result.error)

        return result

    def reset(self) -> None:
        """Clear active demo state. Safe to call between demos."""
        with self._state_lock:
            self._active_mode = DemoMode.NONE
            self._active_result = None
        logger.debug("Demo state reset")

    def get_active_mode(self) -> DemoMode:
        with self._state_lock:
            return self._active_mode

    def get_available_companies(self) -> list[dict]:
        """Return list of available Saudi demo companies for UI display."""
        return [
            {
                "company_id":    p.company_id,
                "name_en":       p.name_en,
                "name_ar":       p.name_ar,
                "sector":        p.sector,
                "sector_ar":     p.sector_ar,
                "employee_count": p.employee_count,
                "saudization_pct": p.saudization_pct,
                "description_en": p.description_en,
                "description_ar": p.description_ar,
            }
            for p in _COMPANY_PROFILES
        ]

    def is_demo_active(self) -> bool:
        with self._state_lock:
            return self._active_mode != DemoMode.NONE

    def is_real_data_safe(self) -> bool:
        """
        Returns True if it is safe to process real data
        (i.e., no demo dataset is currently loaded).
        """
        return not self.is_demo_active()

    # ── Loaders ────────────────────────────────────────────────────────────────

    def _load_attrition(self, company_id: Optional[str]) -> DemoDatasetResult:
        profiles = {p.company_id: p for p in _COMPANY_PROFILES}

        if not company_id:
            # Default to first company
            company_id = list(profiles.keys())[0]

        if company_id not in profiles:
            return DemoDatasetResult(
                success=False,
                demo_mode=DemoMode.SAUDI_ATTRITION,
                company_id=company_id,
                company_name_en=None,
                company_name_ar=None,
                dataset=None,
                row_count=0,
                column_count=0,
                analysis_mode="workforce_stability",
                attrition_modeling_allowed=False,
                readiness_level="BLOCKED",
                governance_notes=[],
                loaded_at=datetime.now(timezone.utc).isoformat(),
                error=f"Unknown demo company: {company_id!r}",
            )

        profile = profiles[company_id]
        df = self._generator.generate(company_id)

        return DemoDatasetResult(
            success=True,
            demo_mode=DemoMode.SAUDI_ATTRITION,
            company_id=company_id,
            company_name_en=profile.name_en,
            company_name_ar=profile.name_ar,
            dataset=df,
            row_count=len(df),
            column_count=len(df.columns),
            analysis_mode="workforce_stability",
            attrition_modeling_allowed=True,
            readiness_level="READY",
            governance_notes=[
                "DEMO MODE: Synthetic data only — not representative of any real organisation.",
                "Attrition modeling permitted for this dataset type.",
                "All proxy constructs available (COR/JD-R/Mobley/Adams).",
            ],
            loaded_at=datetime.now(timezone.utc).isoformat(),
        )

    def _load_jadarat(self) -> DemoDatasetResult:
        df = _generate_jadarat_demo()

        return DemoDatasetResult(
            success=True,
            demo_mode=DemoMode.JADARAT_MARKET,
            company_id=None,
            company_name_en="Jadarat Market Demo",
            company_name_ar="عرض سوق جدارات",
            dataset=df,
            row_count=len(df),
            column_count=len(df.columns),
            analysis_mode="market_intelligence",
            attrition_modeling_allowed=False,
            readiness_level="READY",
            governance_notes=[
                "DEMO MODE: Synthetic job market data — not from real Jadarat portal.",
                "ATTRITION BLOCKED: This dataset contains job postings, not employee records.",
                "Market intelligence analysis available: salary, region, sector, experience.",
                "company identifiers anonymised in demo — real comp_name would be excluded.",
            ],
            loaded_at=datetime.now(timezone.utc).isoformat(),
        )

    def _load_blocked(self) -> DemoDatasetResult:
        df = _generate_governance_blocked_demo()

        return DemoDatasetResult(
            success=True,
            demo_mode=DemoMode.GOVERNANCE_BLOCKED,
            company_id=None,
            company_name_en="Governance Validation Demo",
            company_name_ar="عرض التحقق من الحوكمة",
            dataset=df,
            row_count=len(df),
            column_count=len(df.columns),
            analysis_mode="blocked",
            attrition_modeling_allowed=False,
            readiness_level="BLOCKED",
            governance_notes=[
                "DEMO MODE: This dataset demonstrates governance blocking behavior.",
                "PII DETECTED: national_id, email — these columns block upload.",
                "LEAKAGE DETECTED: resignation_date, termination_date — temporal leakage.",
                "Upload is BLOCKED. PII and leakage columns must be removed before analysis.",
                "This demonstrates the platform's governance-first safety controls.",
            ],
            loaded_at=datetime.now(timezone.utc).isoformat(),
        )


# ── Module-level convenience ──────────────────────────────────────────────────

def get_demo_manager() -> DemoDatasetManager:
    return DemoDatasetManager.get_instance()
