"""
Allocation package — public API.

Import only what the planning service needs:
    from app.services.allocation import AllocationEngine, AllocationResult, validate_plan
"""
from .engine import AllocationEngine
from .models import (
    AllocationMetrics,
    AllocationResult,
    DeferredOrderResult,
    OrderCandidate,
    OutletInfo,
    ServiceAllowance,
    StopPlan,
    TravelData,
    TripResult,
    TripState,
    VehicleCandidate,
)
from .validator import ValidationResult, Violation, validate_plan

__all__ = [
    "AllocationEngine",
    "AllocationMetrics",
    "AllocationResult",
    "DeferredOrderResult",
    "OrderCandidate",
    "OutletInfo",
    "ServiceAllowance",
    "StopPlan",
    "TravelData",
    "TripResult",
    "TripState",
    "VehicleCandidate",
    "ValidationResult",
    "Violation",
    "validate_plan",
]
