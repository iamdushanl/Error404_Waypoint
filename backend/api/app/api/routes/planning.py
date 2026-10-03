from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_role, get_current_user
from app.services.allocation_engine import AllocationEngine, AllocationError

router = APIRouter(prefix="/planning", tags=["planning"])

# --- Models ---
class AllocationRequest(BaseModel):
    order_id: str
    route_id: str

class DeferralRequest(BaseModel):
    order_id: str
    reason: str
    new_delivery_date: Optional[str] = None

# --- Dependencies ---
def get_engine() -> AllocationEngine:
    return AllocationEngine()

# --- Endpoints ---
@router.post("/allocate")
def allocate_order(
    req: AllocationRequest,
    engine: AllocationEngine = Depends(get_engine),
    current_user: Dict[str, Any] = Depends(require_role("dispatcher"))
):
    """
    Validates constraints and allocates an order to a specific route.
    Role required: Dispatcher.
    """
    try:
        result = engine.allocate(req.order_id, req.route_id)
        return {"status": "success", "data": result}
    except AllocationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/validate")
def validate_allocation(
    req: AllocationRequest,
    engine: AllocationEngine = Depends(get_engine),
    current_user: Dict[str, Any] = Depends(require_role("dispatcher"))
):
    """
    Checks if an order CAN be allocated to a route without actually assigning it.
    Useful for UI feedback (e.g. drag-and-drop validation).
    Role required: Dispatcher.
    """
    try:
        valid, message = engine.validate_allocation(req.order_id, req.route_id)
        return {"status": "success", "valid": valid, "message": message}
    except AllocationError as e:
        return {"status": "success", "valid": False, "message": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/defer")
def defer_order(
    req: DeferralRequest,
    engine: AllocationEngine = Depends(get_engine),
    current_user: Dict[str, Any] = Depends(require_role("dispatcher"))
):
    """
    Defers an order that cannot be allocated due to constraints.
    Role required: Dispatcher.
    """
    try:
        result = engine.defer_order(
            req.order_id, 
            current_user["id"],  # Pass the dispatcher ID automatically from auth
            req.reason, 
            req.new_delivery_date
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
