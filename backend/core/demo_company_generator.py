"""
Demo Company Generator — Phase 9.

Produces synthetic, clearly-labeled HR datasets for 5 Saudi enterprise archetypes.
All data is deterministically generated — same seed → same output.
No real employee data. All company names are fictional.

Design rules:
  - Every generated DataFrame carries DEMO_MODE=True metadata
  - All numeric values are plausible but not calibrated to any real enterprise
  - Department names are bilingual (Arabic column 'القسم', English column 'department')
  - No PII: no names, no IDs, no email addresses, no phone numbers
  - Salary values are realistic for KSA private sector (SAR)
  - Returns ready-to-ingest DataFrames compatible with ExcelIngestionEngine
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ── Company archetypes ────────────────────────────────────────────────────────

@dataclass
class DemoCompanyProfile:
    company_id: str
    name_en: str
    name_ar: str
    sector: str
    sector_ar: str
    employee_count: int
    avg_tenure_years: float
    avg_salary_sar: int
    saudization_pct: float           # 0–100
    attrition_base_rate: float       # 0–1
    departments: list[dict]          # [{"en": ..., "ar": ..., "size_pct": ..., "risk_multiplier": ...}]
    description_en: str = ""
    description_ar: str = ""
    metadata: dict = field(default_factory=dict)


_COMPANY_PROFILES: list[DemoCompanyProfile] = [
    DemoCompanyProfile(
        company_id="national-industrial-holdings",
        name_en="National Industrial Holdings Co.",
        name_ar="الشركة الوطنية للصناعة القابضة",
        sector="Heavy Industry",
        sector_ar="الصناعات الثقيلة",
        employee_count=3247,
        avg_tenure_years=4.8,
        avg_salary_sar=14_500,
        saudization_pct=62.4,
        attrition_base_rate=0.18,
        departments=[
            {"en": "Operations",          "ar": "العمليات",                "size_pct": 0.30, "risk_multiplier": 1.3},
            {"en": "Engineering",         "ar": "الهندسة",                 "size_pct": 0.22, "risk_multiplier": 0.8},
            {"en": "Finance & Accounting","ar": "المالية والمحاسبة",        "size_pct": 0.10, "risk_multiplier": 0.6},
            {"en": "Human Resources",     "ar": "الموارد البشرية",          "size_pct": 0.06, "risk_multiplier": 0.7},
            {"en": "Information Technology","ar": "تقنية المعلومات",        "size_pct": 0.12, "risk_multiplier": 1.5},
            {"en": "Supply Chain",        "ar": "سلسلة التوريد",            "size_pct": 0.10, "risk_multiplier": 1.1},
            {"en": "Quality Assurance",   "ar": "ضمان الجودة",             "size_pct": 0.07, "risk_multiplier": 0.9},
            {"en": "Legal & Compliance",  "ar": "الشؤون القانونية والامتثال","size_pct": 0.03, "risk_multiplier": 0.5},
        ],
        description_en="Large industrial conglomerate with diversified manufacturing operations across the Kingdom.",
        description_ar="مجموعة صناعية كبرى ذات عمليات تصنيع متنوعة في أرجاء المملكة.",
    ),
    DemoCompanyProfile(
        company_id="saudi-digital-services",
        name_en="Saudi Digital Services Group",
        name_ar="مجموعة الخدمات الرقمية السعودية",
        sector="Technology & Telecoms",
        sector_ar="التقنية والاتصالات",
        employee_count=1850,
        avg_tenure_years=2.9,
        avg_salary_sar=18_200,
        saudization_pct=45.1,
        attrition_base_rate=0.28,
        departments=[
            {"en": "Software Engineering", "ar": "هندسة البرمجيات",         "size_pct": 0.35, "risk_multiplier": 1.7},
            {"en": "Product Management",   "ar": "إدارة المنتجات",           "size_pct": 0.12, "risk_multiplier": 1.2},
            {"en": "Data & AI",            "ar": "البيانات والذكاء الاصطناعي","size_pct": 0.15, "risk_multiplier": 1.9},
            {"en": "Customer Success",     "ar": "نجاح العملاء",             "size_pct": 0.18, "risk_multiplier": 1.0},
            {"en": "Sales",                "ar": "المبيعات",                 "size_pct": 0.10, "risk_multiplier": 1.3},
            {"en": "Finance",              "ar": "المالية",                  "size_pct": 0.06, "risk_multiplier": 0.5},
            {"en": "Human Resources",      "ar": "الموارد البشرية",          "size_pct": 0.04, "risk_multiplier": 0.6},
        ],
        description_en="Fast-growing technology services company serving Saudi government and private sector digital transformation.",
        description_ar="شركة خدمات تقنية سريعة النمو تخدم التحول الرقمي للقطاعين الحكومي والخاص في المملكة.",
    ),
    DemoCompanyProfile(
        company_id="riyadh-healthcare-network",
        name_en="Riyadh Healthcare Network",
        name_ar="شبكة الرياض الصحية",
        sector="Healthcare",
        sector_ar="الرعاية الصحية",
        employee_count=4120,
        avg_tenure_years=5.6,
        avg_salary_sar=16_800,
        saudization_pct=71.3,
        attrition_base_rate=0.14,
        departments=[
            {"en": "Clinical Operations",  "ar": "العمليات السريرية",        "size_pct": 0.40, "risk_multiplier": 1.1},
            {"en": "Nursing",              "ar": "التمريض",                  "size_pct": 0.25, "risk_multiplier": 1.4},
            {"en": "Administration",       "ar": "الإدارة",                  "size_pct": 0.12, "risk_multiplier": 0.7},
            {"en": "Pharmacy",             "ar": "الصيدلة",                  "size_pct": 0.08, "risk_multiplier": 0.8},
            {"en": "Radiology & Imaging",  "ar": "الأشعة والتصوير الطبي",    "size_pct": 0.07, "risk_multiplier": 0.9},
            {"en": "Information Technology","ar": "تقنية المعلومات",         "size_pct": 0.05, "risk_multiplier": 1.6},
            {"en": "Finance",              "ar": "المالية",                  "size_pct": 0.03, "risk_multiplier": 0.5},
        ],
        description_en="Leading multi-specialty hospital network serving greater Riyadh with 8 facilities.",
        description_ar="شبكة مستشفيات متخصصة رائدة تخدم منطقة الرياض الكبرى بـ8 مرافق.",
    ),
    DemoCompanyProfile(
        company_id="gulf-retail-operations",
        name_en="Gulf Retail Operations Ltd.",
        name_ar="شركة عمليات التجزئة الخليجية",
        sector="Retail",
        sector_ar="التجزئة",
        employee_count=6800,
        avg_tenure_years=2.1,
        avg_salary_sar=8_400,
        saudization_pct=38.7,
        attrition_base_rate=0.34,
        departments=[
            {"en": "Store Operations",    "ar": "عمليات المتاجر",           "size_pct": 0.55, "risk_multiplier": 1.6},
            {"en": "Logistics",           "ar": "اللوجستيات",              "size_pct": 0.18, "risk_multiplier": 1.4},
            {"en": "Merchandising",       "ar": "التسويق السلعي",           "size_pct": 0.10, "risk_multiplier": 1.0},
            {"en": "Human Resources",     "ar": "الموارد البشرية",          "size_pct": 0.05, "risk_multiplier": 0.7},
            {"en": "Finance",             "ar": "المالية",                  "size_pct": 0.05, "risk_multiplier": 0.6},
            {"en": "E-Commerce",          "ar": "التجارة الإلكترونية",      "size_pct": 0.07, "risk_multiplier": 1.8},
        ],
        description_en="Large retail chain with 180+ outlets across Saudi Arabia and GCC.",
        description_ar="سلسلة تجزئة كبرى تضم أكثر من 180 منفذاً في المملكة العربية السعودية ودول الخليج.",
    ),
    DemoCompanyProfile(
        company_id="public-sector-workforce-authority",
        name_en="Public Sector Workforce Authority (Simulated)",
        name_ar="هيئة القوى العاملة في القطاع العام (محاكاة)",
        sector="Government",
        sector_ar="القطاع الحكومي",
        employee_count=2350,
        avg_tenure_years=8.3,
        avg_salary_sar=13_200,
        saudization_pct=94.5,
        attrition_base_rate=0.07,
        departments=[
            {"en": "Strategy & Planning",  "ar": "الاستراتيجية والتخطيط",   "size_pct": 0.15, "risk_multiplier": 0.6},
            {"en": "Workforce Development","ar": "تطوير القوى العاملة",      "size_pct": 0.25, "risk_multiplier": 0.8},
            {"en": "Regulatory Affairs",   "ar": "الشؤون التنظيمية",        "size_pct": 0.20, "risk_multiplier": 0.7},
            {"en": "Digital Services",     "ar": "الخدمات الرقمية",         "size_pct": 0.18, "risk_multiplier": 1.2},
            {"en": "Public Relations",     "ar": "العلاقات العامة",          "size_pct": 0.10, "risk_multiplier": 0.5},
            {"en": "Finance & Audit",      "ar": "المالية والتدقيق",         "size_pct": 0.12, "risk_multiplier": 0.4},
        ],
        description_en="Government authority responsible for national workforce policy and Saudization programs.",
        description_ar="جهة حكومية مسؤولة عن سياسة القوى العاملة الوطنية وبرامج السعودة.",
    ),
]


# ── Generator ─────────────────────────────────────────────────────────────────

class DemoCompanyGenerator:
    """
    Generates synthetic HR datasets for demo company profiles.

    Usage:
        gen = DemoCompanyGenerator()
        profiles = gen.list_profiles()
        df = gen.generate(company_id="national-industrial-holdings")
        df_ar = gen.generate(company_id="saudi-digital-services", language="ar")
    """

    def list_profiles(self) -> list[dict]:
        return [
            {
                "company_id": p.company_id,
                "name_en": p.name_en,
                "name_ar": p.name_ar,
                "sector": p.sector,
                "sector_ar": p.sector_ar,
                "employee_count": p.employee_count,
                "description_en": p.description_en,
                "description_ar": p.description_ar,
            }
            for p in _COMPANY_PROFILES
        ]

    def get_profile(self, company_id: str) -> Optional[DemoCompanyProfile]:
        for p in _COMPANY_PROFILES:
            if p.company_id == company_id:
                return p
        return None

    def generate(
        self,
        company_id: str,
        language: str = "en",
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        Generate a synthetic HR dataset for the specified demo company.

        Args:
            company_id: One of the registered demo company IDs
            language: 'en' for English column headers, 'ar' for Arabic
            seed: Random seed for reproducible output

        Returns:
            pd.DataFrame with synthetic HR data, clearly marked as DEMO in attrs
        """
        profile = self.get_profile(company_id)
        if profile is None:
            available = [p.company_id for p in _COMPANY_PROFILES]
            raise ValueError(
                f"Unknown demo company: {company_id!r}. "
                f"Available: {available}"
            )

        rng = np.random.default_rng(seed)
        random.seed(seed)

        rows = []
        for dept_info in profile.departments:
            dept_size = max(1, int(profile.employee_count * dept_info["size_pct"]))
            risk_mult = dept_info["risk_multiplier"]

            for _ in range(dept_size):
                tenure = max(0.1, rng.exponential(profile.avg_tenure_years))
                job_level = int(np.clip(rng.choice([1, 2, 3, 4, 5], p=[0.25, 0.35, 0.25, 0.10, 0.05]), 1, 5))
                salary_base = profile.avg_salary_sar * (0.6 + 0.15 * job_level)
                salary = max(3000, int(rng.normal(salary_base, salary_base * 0.15)))
                perf_rating = float(np.clip(rng.normal(3.2, 0.6), 1.0, 5.0))
                training_hours = max(0, int(rng.poisson(24)))
                overtime_hours = max(0, int(rng.poisson(6)))
                is_saudi = rng.random() < (profile.saudization_pct / 100)
                satisfaction = float(np.clip(rng.normal(3.5 - risk_mult * 0.3, 0.7), 1.0, 5.0))
                engagement = float(np.clip(rng.normal(3.4 - risk_mult * 0.2, 0.6), 1.0, 5.0))
                team_size = max(2, int(rng.normal(8, 3)))
                last_promotion_months = max(0, int(rng.exponential(18)))
                flight_risk = float(np.clip(
                    rng.normal(
                        profile.attrition_base_rate * risk_mult,
                        0.08,
                    ), 0.0, 1.0
                ))

                row = {
                    "dept_en": dept_info["en"],
                    "dept_ar": dept_info["ar"],
                    "tenure_years": round(tenure, 1),
                    "job_level": job_level,
                    "salary_sar": salary,
                    "performance_rating": round(perf_rating, 2),
                    "training_hours_ytd": training_hours,
                    "overtime_hours_monthly": overtime_hours,
                    "is_saudi": int(is_saudi),
                    "satisfaction_score": round(satisfaction, 2),
                    "engagement_score": round(engagement, 2),
                    "team_size": team_size,
                    "months_since_promotion": last_promotion_months,
                    "flight_risk": round(flight_risk, 3),
                }
                rows.append(row)

        df = pd.DataFrame(rows)

        # Apply language preference for column names
        if language == "ar":
            df = df.rename(columns={
                "dept_en": "القسم_en",
                "dept_ar": "القسم",
                "tenure_years": "سنوات_الخدمة",
                "job_level": "المستوى_الوظيفي",
                "salary_sar": "الراتب_ريال",
                "performance_rating": "تقييم_الأداء",
                "training_hours_ytd": "ساعات_التدريب",
                "overtime_hours_monthly": "ساعات_العمل_الإضافي",
                "is_saudi": "سعودي",
                "satisfaction_score": "درجة_الرضا",
                "engagement_score": "درجة_الالتزام",
                "team_size": "حجم_الفريق",
                "months_since_promotion": "أشهر_منذ_الترقية",
                "flight_risk": "مخاطر_المغادرة",
            })
        else:
            df = df.rename(columns={"dept_en": "department", "dept_ar": "department_ar"})

        # Tag as demo data — never silently pass as real
        df.attrs["DEMO_MODE"] = True
        df.attrs["company_id"] = profile.company_id
        df.attrs["company_name_en"] = profile.name_en
        df.attrs["company_name_ar"] = profile.name_ar
        df.attrs["sector"] = profile.sector
        df.attrs["synthetic_seed"] = seed
        df.attrs["language"] = language

        return df

    def generate_bytes(
        self,
        company_id: str,
        language: str = "en",
        file_format: str = "csv",
        seed: int = 42,
    ) -> tuple[bytes, str]:
        """
        Generate demo data as raw bytes suitable for passing to ExcelIngestionEngine.

        Returns:
            (raw_bytes, filename)
        """
        import io
        df = self.generate(company_id=company_id, language=language, seed=seed)

        profile = self.get_profile(company_id)
        safe_name = company_id.replace("-", "_")

        if file_format == "csv":
            buf = io.BytesIO()
            df.to_csv(buf, index=False, encoding="utf-8-sig")
            return buf.getvalue(), f"demo_{safe_name}.csv"
        elif file_format == "xlsx":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Employee Data")
            return buf.getvalue(), f"demo_{safe_name}.xlsx"
        elif file_format == "parquet":
            buf = io.BytesIO()
            df.to_parquet(buf, index=False)
            return buf.getvalue(), f"demo_{safe_name}.parquet"
        else:
            raise ValueError(f"Unsupported format: {file_format!r}. Use 'csv', 'xlsx', or 'parquet'.")
