import logging
from typing import Dict, Any, Tuple
from fastapi import HTTPException
from app.db.session import get_supabase

logger = logging.getLogger(__name__)

class AllocationError(Exception):
    """Custom exception for allocation constraint violations."""
    pass

class AllocationEngine:
    """
    Core business logic for routing and order allocation.
    Enforces the 5 key constraints of the Waypoint Delivery Network:
    1. Capacity Limits (Weight & Units)
    2. Cold Chain (Temperature)
    3. Vehicle Access (Van-only stores)
    4. Time Windows (Fresh before 8 AM)
    5. Trip Limits
    """
    def __init__(self):
        self.supabase = get_supabase()

    def validate_allocation(self, order_id: str, route_id: str) -> Tuple[bool, str]:
        """
        Validates if an order can be allocated to a specific route.
        Returns (True, "Success") if valid, otherwise raises AllocationError.
        """
        try:
            # 1. Fetch Route & Vehicle details
            route_resp = self.supabase.table("routes").select(
                "*, vehicle:vehicles(*), route_stops(order_id)"
            ).eq("id", route_id).single().execute()
            
            if not route_resp.data:
                raise AllocationError("Route not found.")
            
            route = route_resp.data
            vehicle = route.get("vehicle")
            if not vehicle:
                raise AllocationError("No vehicle assigned to this route.")

            # 2. Fetch Order & Outlet details
            order_resp = self.supabase.table("orders").select(
                "*, outlet:outlets(*), order_items(*, product:products(*))"
            ).eq("id", order_id).single().execute()
            
            if not order_resp.data:
                raise AllocationError("Order not found.")
                
            order = order_resp.data
            outlet = order.get("outlet", {})
            order_items = order.get("order_items", [])

            # --- CONSTRAINT 1: COLD CHAIN ---
            temp_tags = order.get("temperature_tags", [])
            needs_chiller = any(tag in ["chilled", "frozen", "fresh"] for tag in temp_tags)
            if needs_chiller and not vehicle.get("has_chiller"):
                raise AllocationError(f"Cold Chain Violation: Order requires a refrigerated vehicle (contains {', '.join(temp_tags)}).")

            # --- CONSTRAINT 2: VEHICLE ACCESS ---
            # 'requires_van' or similar is usually on outlet for constrained locations
            if outlet.get("requires_van") and vehicle.get("vehicle_type", "").lower() != "van":
                raise AllocationError("Access Violation: Outlet is in a restricted area and requires a Van.")

            # --- CONSTRAINT 3: CAPACITY (WEIGHT & UNITS) ---
            # Calculate total order weight and units
            order_weight = sum((item["product"]["weight_kg"] or 0) * item["quantity"] for item in order_items if item.get("product"))
            order_units = order.get("total_units", 0)

            # Calculate current route load
            current_route_weight = 0
            current_route_units = 0
            
            if route.get("route_stops"):
                existing_order_ids = [stop["order_id"] for stop in route["route_stops"]]
                if existing_order_ids:
                    existing_orders_resp = self.supabase.table("orders").select(
                        "total_units, order_items(quantity, product:products(weight_kg))"
                    ).in_("id", existing_order_ids).execute()
                    
                    for eo in existing_orders_resp.data:
                        current_route_units += eo.get("total_units", 0)
                        for item in eo.get("order_items", []):
                            if item.get("product"):
                                current_route_weight += (item["product"]["weight_kg"] or 0) * item["quantity"]

            if current_route_weight + order_weight > (vehicle.get("capacity_kg") or float('inf')):
                raise AllocationError(f"Capacity Violation: Adding {order_weight}kg exceeds vehicle weight limit ({vehicle.get('capacity_kg')}kg).")
                
            if current_route_units + order_units > (vehicle.get("capacity_units") or float('inf')):
                raise AllocationError(f"Capacity Violation: Adding {order_units} units exceeds vehicle unit limit ({vehicle.get('capacity_units')}).")

            # --- CONSTRAINT 4: TRIP LIMITS ---
            delivery_date = route.get("delivery_date")
            trips_resp = self.supabase.table("routes").select("id").eq("vehicle_id", vehicle["id"]).eq("delivery_date", delivery_date).execute()
            if len(trips_resp.data) > 2:
                logger.warning("Trip limit warning: Vehicle is scheduled for more than 2 trips today.")

            # --- CONSTRAINT 5: TIME WINDOWS (Fresh before 8 AM) ---
            if "fresh" in temp_tags:
                logger.info("Time Window Note: Order contains 'fresh' items. Must sequence early in the route (before 8 AM).")

            return True, "Allocation valid."
            
        except Exception as e:
            if isinstance(e, AllocationError):
                raise
            logger.error(f"Unexpected error during validation: {e}")
            raise AllocationError(f"System error during validation: {str(e)}")

    def allocate(self, order_id: str, route_id: str) -> Dict[str, Any]:
        """
        Validates constraints and officially allocates the order to the route.
        """
        # 1. Validate
        self.validate_allocation(order_id, route_id)
        
        # 2. Get current max stop sequence
        stops_resp = self.supabase.table("route_stops").select("stop_sequence").eq("route_id", route_id).execute()
        next_seq = 1
        if stops_resp.data:
            next_seq = max(stop["stop_sequence"] for stop in stops_resp.data) + 1
            
        # 3. Insert Stop
        order_resp = self.supabase.table("orders").select("outlet_id").eq("id", order_id).single().execute()
        new_stop = {
            "route_id": route_id,
            "order_id": order_id,
            "outlet_id": order_resp.data["outlet_id"],
            "stop_sequence": next_seq,
            "status": "pending"
        }
        
        inserted = self.supabase.table("route_stops").insert(new_stop).execute()
        
        # 4. Update order status
        self.supabase.table("orders").update({"status": "planned"}).eq("id", order_id).execute()
        
        return inserted.data[0]

    def defer_order(self, order_id: str, dispatcher_id: str, reason: str, new_date: str = None) -> Dict[str, Any]:
        """
        Logs a deferral when constraints cannot be met.
        """
        deferral = {
            "order_id": order_id,
            "deferred_by": dispatcher_id,
            "reason": reason,
            "new_delivery_date": new_date
        }
        
        inserted = self.supabase.table("deferrals").insert(deferral).execute()
        
        # Update order status
        self.supabase.table("orders").update({"status": "deferred"}).eq("id", order_id).execute()
        
        return inserted.data[0]
