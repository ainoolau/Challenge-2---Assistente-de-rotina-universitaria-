"""Fachada de compatibilidade para o motor determinístico em `src/core/planning.py`."""

from src.core.planning import (
    PlanningContext,
    audit_plan,
    audit_rebalance,
    detect_input_conflicts,
    expand_sleep_slots,
    free_windows,
    input_conflicts,
    overlaps,
    plan,
    protected_slots,
    rebalance,
)

__all__ = [
    "PlanningContext",
    "audit_plan",
    "audit_rebalance",
    "detect_input_conflicts",
    "expand_sleep_slots",
    "free_windows",
    "input_conflicts",
    "overlaps",
    "plan",
    "protected_slots",
    "rebalance",
]
