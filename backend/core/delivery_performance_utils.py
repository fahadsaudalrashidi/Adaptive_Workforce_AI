"""
Delivery / On-Time Performance — shared computation utility.

Extracted during Phase 34 (Logistics Intelligence) from Phase 33's
`procurement_intelligence_engine.py`, whose inbound-supplier-delivery
on-time calculation (expected date vs. actual date, grouped by an entity
name) is EXACTLY the same computation Logistics needs for outbound-carrier
delivery performance — only the grouping entity differs (supplier vs.
carrier) and the two field's real-world meaning differs (a supplier
delivering TO this platform's owner vs. this platform's owner delivering
TO their own customers via a carrier). Rather than duplicate the on-time
arithmetic a second time, both `procurement_intelligence_engine.py`'s
`_delivery_from_lines()` and `logistics_intelligence_engine.py`'s
delivery-performance function call this one shared, domain-agnostic
utility and map its generic output into their own domain-specific result
dataclasses (`SupplierDeliveryItem` / `CarrierDeliveryItem`) — so each
module's public API and field names stay meaningful to its own domain
while the actual computation is written and tested once.

On-time definition: `actual_date <= expected_date` (no grace-period
tolerance — a same-day delivery counts as on-time, a delivery arriving any
time after the expected date counts as late). This is a deliberately
simple, disclosed definition, not a configurable SLA engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import pandas as pd


@dataclass(frozen=True)
class GroupOnTimeStats:
    group: str
    n_with_complete_dates: int
    n_on_time: int
    on_time_pct: float


@dataclass(frozen=True)
class OnTimePerformanceResult:
    available: bool
    reason: Optional[str]
    n_groups_without_data: int
    groups_without_data: list[str]
    items: list[GroupOnTimeStats]


def unavailable_on_time_performance_result(reason: str) -> OnTimePerformanceResult:
    return OnTimePerformanceResult(
        available=False, reason=reason, n_groups_without_data=0, groups_without_data=[], items=[],
    )


def compute_on_time_performance(
    rows: Sequence[tuple[str, Optional[pd.Timestamp], Optional[pd.Timestamp]]],
) -> OnTimePerformanceResult:
    """
    rows: sequence of (group_key, expected_date, actual_date). group_key is
    the supplier/carrier/etc. name; expected_date/actual_date are
    pandas Timestamps or None. Groups where NO row has both dates present
    are reported separately (`groups_without_data`), never silently
    dropped or defaulted to some on-time percentage.
    """
    if not rows:
        return unavailable_on_time_performance_result(
            "No rows were provided for on-time performance calculation.",
        )

    all_groups = {g for g, _, _ in rows}
    complete = [(g, exp, act) for g, exp, act in rows if exp is not None and act is not None]
    groups_with_data = {g for g, _, _ in complete}
    groups_without = sorted(all_groups - groups_with_data)

    if not complete:
        return unavailable_on_time_performance_result(
            "Expected/actual delivery-date columns were detected, but no row had both a valid "
            "expected and actual date.",
        )

    by_group: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for g, exp, act in complete:
        by_group.setdefault(g, []).append((exp, act))

    items = []
    for group, pairs in by_group.items():
        n_on_time = sum(1 for exp, act in pairs if act <= exp)
        items.append(GroupOnTimeStats(
            group=group, n_with_complete_dates=len(pairs), n_on_time=n_on_time,
            on_time_pct=round(100.0 * n_on_time / len(pairs), 1),
        ))
    items.sort(key=lambda i: i.on_time_pct)

    return OnTimePerformanceResult(
        available=True, reason=None, n_groups_without_data=len(groups_without),
        groups_without_data=groups_without, items=items,
    )
