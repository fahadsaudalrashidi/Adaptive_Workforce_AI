# Architecture Diagrams — Phase 8

**Document Type:** Visual Architecture Reference  
**Phase:** 8 — Executive Enterprise Presentation & Market Dominance  
**Date:** 2026-05-20  
**Format:** Mermaid diagrams (render with any Mermaid-compatible viewer)

---

## Diagram 1 — System Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        EU[Executive UI\nReact + TypeScript\nTailwind + Recharts]
        SL[Streamlit Interface\nOperational Analysis]
    end

    subgraph "API Gateway Layer"
        GW[FastAPI Router\n/v1 Enterprise Routes\nGovernanceStatus on all responses]
        AUTH[JWT Auth\nTenant Claim Validation\n⚠ Pending implementation]
    end

    subgraph "Governance Layer — NEVER BYPASSED"
        ESV[ExportSafetyValidator\nPII removal · Disclaimer attachment\nLanguage validation]
        ELG[EnterpriseLanguageGuard\nDeterministic claim detection\nSafe-text rewriting]
        ALG[AuditLogger\n18 event types · PII-safe summaries\nImmutable entries]
    end

    subgraph "Core Analytics Pipeline"
        OBP[EnterpriseOnboardingPipeline\n7-stage validation]
        TAF[TheoryAwareFeatureEngine\nCOR · JD-R · FFM · Mobley · Adams]
        CAL[CalibrationEngine\nECE · Brier · AUC validation]
        ERL[ExecutiveReportingLayer\nAggregate-only outputs]
    end

    subgraph "Tenant Infrastructure"
        TC[TenantContext\nNamespace isolation]
        TIG[TenantIsolationGuard\nCross-tenant enforcement]
        ARG[ArtifactRegistry\nSensitivity classification\nTraceability required]
    end

    subgraph "Configuration Lock"
        PS[ProductionSettings\n11 governance constants\nNon-overridable]
    end

    subgraph "Storage — Phase 7 in-memory, Production: persistent"
        DS[(Dataset Store)]
        MS[(Model Store)]
        AL[(Audit Log)]
        AR[(Artifact Registry)]
    end

    EU --> GW
    SL --> GW
    GW --> AUTH
    AUTH --> TC
    TC --> TIG
    TIG --> OBP
    OBP --> TAF
    TAF --> CAL
    CAL --> ERL
    ERL --> ESV
    ESV --> ELG
    ESV --> ALG
    ALG --> AL
    ARG --> AR
    TC --> DS
    TC --> MS
    PS -. enforced at startup .-> GW

    style ESV fill:#1e40af,color:#fff
    style ALG fill:#1e40af,color:#fff
    style ELG fill:#1e40af,color:#fff
    style PS fill:#7c3aed,color:#fff
    style AUTH fill:#b45309,color:#fff
```

---

## Diagram 2 — Governance Pipeline Flow

```mermaid
flowchart LR
    IN([Raw Dataset\nUpload]) --> S1

    subgraph "Stage 1: Schema Intelligence"
        S1[SaudiSchemaIntelligenceEngine\n· ERP detection\n· PII column scan\n· Leakage column detection]
    end

    S1 -->|Schema valid| S2
    S1 -->|BLOCKED| BK1([❌ BLOCKED\nSchema violation])

    subgraph "Stage 2: Saudi Data Governance"
        S2[SaudiDataGovernanceEngine\n· PDPL column screening\n· Arabic field detection\n· Nitaqat/Mudad support]
    end

    S2 -->|Governance OK| S3
    S2 -->|BLOCKED| BK2([❌ BLOCKED\nPDPL violation])

    subgraph "Stage 3: Temporal Validation"
        S3[TemporalValidator\n· Training/test split\n· Future-leakage prevention\n· Holdout window enforcement]
    end

    S3 -->|Valid| S4
    S3 -->|BLOCKED| BK3([❌ BLOCKED\nTemporal leakage])

    subgraph "Stage 4: Theory Compatibility"
        S4[TheoryAwareColumnMapper\n· COR construct mapping\n· JD-R construct mapping\n· FFM/Mobley/Equity constructs]
    end

    S4 -->|Compatible| S5

    subgraph "Stage 5: Calibration Validation"
        S5[CalibrationEngine\n· ECE threshold check\n· Brier score validation\n· AUC-ROC assessment]
    end

    S5 -->|Calibrated| S6

    subgraph "Stage 6: Language Safety"
        S6[EnterpriseLanguageGuard\n· Deterministic claim detection\n· Safe-text rewriting\n· Governance framing]
    end

    S6 -->|Safe| S7

    subgraph "Stage 7: Export Safety"
        S7[ExportSafetyValidator\n· PII field removal\n· Disclaimer attachment\n· PDPL note attachment]
    end

    S7 --> OUT([✅ SafeExportPackage\n+ GovernanceDisclaimer\n+ ConfidenceWarning\n+ PDPLNote])

    style S1 fill:#1e3a8a,color:#fff
    style S2 fill:#1e3a8a,color:#fff
    style S3 fill:#1e3a8a,color:#fff
    style S4 fill:#0e7490,color:#fff
    style S5 fill:#0e7490,color:#fff
    style S6 fill:#7c3aed,color:#fff
    style S7 fill:#7c3aed,color:#fff
    style OUT fill:#059669,color:#fff
    style BK1 fill:#dc2626,color:#fff
    style BK2 fill:#dc2626,color:#fff
    style BK3 fill:#dc2626,color:#fff
```

---

## Diagram 3 — Theory-to-ML Flow

```mermaid
flowchart TB
    subgraph "Peer-Reviewed Theory Foundation"
        T1["COR Theory\nHobfoll (1989)\nJournal of Applied Psychology"]
        T2["JD-R Model\nBakker & Demerouti (2007)\nJournal of Managerial Psychology"]
        T3["Five Factor Model\nMcCrae & Costa (1987)\nJPSP"]
        T4["Mobley Process\nMobley (1977)\nJournal of Applied Psychology"]
        T5["Adams Equity Theory\nAdams (1963)\nJournal of Abnormal Psychology"]
    end

    subgraph "Construct Engineering"
        C1[SatisfactionIndex\nBurnoutRisk\nEngagementScore]
        C2[CareerProgression\nSalaryGrowth\nTenureRatio]
        C3[IncomePerLevel\nEngagementScore]
        C4[SatisfactionIndex\nTenureRatio]
        C5[IncomePerLevel\nCareerProgression]
    end

    subgraph "Validated Feature Set"
        VF[7 Theory-Grounded Constructs\nZero leakage columns\nZero legacy proxies\nZero attendance heuristics]
    end

    subgraph "Model Training"
        MT[CatBoost / LightGBM\nTemporal holdout validation\nCalibration-required pass]
    end

    subgraph "Calibrated Output"
        CO[Probability Scores\nECE < 0.05\nBrier < 0.20\nAUC > 0.75]
    end

    subgraph "Executive Output — Aggregate Only"
        EO[Department Stability Bands\nWorkforce Stability Index\nTheory Contribution Analysis\nStrategic Retention Insights]
    end

    T1 --> C1
    T2 --> C2
    T3 --> C3
    T4 --> C4
    T5 --> C5
    C1 & C2 & C3 & C4 & C5 --> VF
    VF --> MT
    MT --> CO
    CO --> EO

    style VF fill:#1e40af,color:#fff
    style CO fill:#0e7490,color:#fff
    style EO fill:#059669,color:#fff
```

---

## Diagram 4 — PDPL Compliance Flow

```mermaid
flowchart TB
    IN([Data Enters Platform]) --> CHECK1

    CHECK1{Contains Saudi\nEmployee Data?}
    CHECK1 -->|Yes| PDPL1
    CHECK1 -->|No| STD[Standard Processing]

    subgraph "PDPL Controls Layer"
        PDPL1[PII Column Detection\n· National ID · Iqama · IBAN\n· Phone · Email · Passport\n· Arabic field variants]
        PDPL1 --> PDPL2[Data Minimization\n· Strip PII before any processing\n· Aggregate only — no individual output\n· Employee-level disabled by config lock]
        PDPL2 --> PDPL3[Purpose Limitation\n· Analytics for workforce stability only\n· No automated HR decisions\n· No individual risk score in export]
        PDPL3 --> PDPL4[Accountability Trail\n· AuditLogger records all processing\n· Tenant-scoped access control\n· PII-safe audit summaries]
        PDPL4 --> PDPL5[Data Subject Rights\n· PDPL review note on every export\n· No re-identification possible\n· Retention period recorded per artifact]
    end

    PDPL5 --> NOTE["⚠ LEGAL NOTE\nTechnical controls implemented.\nLegal compliance certification requires\nqualified Saudi legal counsel review.\nSDC/SDAIA registration may be required."]

    STD --> OUT([✅ Safe Output])
    NOTE --> OUT

    style PDPL1 fill:#1e3a8a,color:#fff
    style PDPL2 fill:#1e40af,color:#fff
    style PDPL3 fill:#1e40af,color:#fff
    style PDPL4 fill:#1e40af,color:#fff
    style PDPL5 fill:#0e7490,color:#fff
    style NOTE fill:#b45309,color:#fff
```

---

## Diagram 5 — SaaS Multi-Tenant Architecture

```mermaid
graph TB
    subgraph "Tenant A — Aramco-scale"
        TA_CTX[TenantContext\ntenants/aramco-sim/...]
        TA_DS[(Datasets\ntenants/aramco-sim/datasets/)]
        TA_MDL[(Models\ntenants/aramco-sim/models/)]
        TA_AUD[(Audit Log\ntenants/aramco-sim/audit/)]
    end

    subgraph "Tenant B — STC-scale"
        TB_CTX[TenantContext\ntenants/stc-sim/...]
        TB_DS[(Datasets\ntenants/stc-sim/datasets/)]
        TB_MDL[(Models\ntenants/stc-sim/models/)]
        TB_AUD[(Audit Log\ntenants/stc-sim/audit/)]
    end

    subgraph "Tenant C — Ministry"
        TC_CTX[TenantContext\ntenants/ministry-sim/...]
        TC_DS[(Datasets)]
        TC_MDL[(Models)]
        TC_AUD[(Audit Log)]
    end

    subgraph "Shared Platform Services"
        GW[API Gateway\nJWT Tenant Claim Validation]
        TIG[TenantIsolationGuard\nCrossing = PermissionError]
        PS[ProductionSettings\n11 Governance Locks]
        ESV[ExportSafetyValidator\nAll exports pass through]
        ALG[AuditLogger\nTenant-scoped access]
    end

    GW --> TIG
    TIG --> TA_CTX
    TIG --> TB_CTX
    TIG --> TC_CTX
    TA_CTX --> TA_DS & TA_MDL & TA_AUD
    TB_CTX --> TB_DS & TB_MDL & TB_AUD
    TC_CTX --> TC_DS & TC_MDL & TC_AUD
    PS -. locks applied globally .-> GW
    ESV -. all exports .-> GW
    ALG -. all events .-> TA_AUD & TB_AUD & TC_AUD

    TA_CTX -.cross-tenant blocked.- TB_CTX
    TA_CTX -.cross-tenant blocked.- TC_CTX

    style TIG fill:#dc2626,color:#fff
    style PS fill:#7c3aed,color:#fff
    style ESV fill:#1e40af,color:#fff
```

---

## Diagram 6 — Security & Audit Flow

```mermaid
sequenceDiagram
    actor CIO as CIO / CHRO
    participant API as API Gateway
    participant AUTH as JWT Validator
    participant TIG as TenantIsolationGuard
    participant PIPE as Analytics Pipeline
    participant ESV as ExportSafetyValidator
    participant AUD as AuditLogger

    CIO->>API: POST /v1/tenants/{id}/reports/executive
    API->>AUTH: Validate Bearer token
    AUTH-->>API: tenant_id = "acme-corp"
    API->>TIG: assert_access("acme-corp", path_tenant_id)
    TIG-->>API: ✓ Access granted

    API->>PIPE: Generate executive report
    PIPE-->>API: Aggregate stability analysis

    API->>ESV: validate_and_sanitize(report_data)
    ESV->>ESV: Remove PII fields
    ESV->>ESV: Correct language violations
    ESV->>ESV: Attach 3 mandatory disclaimers
    ESV-->>API: SafeExportPackage

    API->>AUD: log_event(EVT_REPORT_GENERATED, tenant="acme-corp")
    AUD->>AUD: Assert no PII in summary
    AUD->>AUD: Strip DataFrame keys from metadata
    AUD-->>API: ✓ Logged

    API-->>CIO: SafeExportPackage + GovernanceStatus
    Note over CIO: Response includes:<br/>governance_disclaimer<br/>confidence_warning<br/>pdpl_note<br/>governance_status: "OK"
```

---

*All diagrams represent the implemented architecture as of Phase 7/8. Authentication (JWT) is a placeholder pending implementation. Persistent storage is in-memory pending infrastructure integration.*
