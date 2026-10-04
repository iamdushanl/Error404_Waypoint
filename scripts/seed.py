"""
Waypoint — database seed script.
Phase 2: Seeds outlets, vehicles, calendar, and the four demo user accounts.

Usage:
    cd backend/api
    py seed.py                    # reads data/*.csv relative to repo root
    py seed.py --data-dir /path   # custom CSV directory

Requirements:
    pip install -r requirements.txt

Environment:
    Reads from .env (or environment variables):
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY   ← required; never use the anon key here
    - SUPABASE_ANON_KEY           ← used only to create auth users

Competition data terms:
    The CSV files are confidential. Do not commit them to the repository.
    Place them in data/ (gitignored) before running this script.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from repo root ──────────────────────────────────────────────────
# scripts/seed.py is one level below repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

from supabase import create_client, Client  # noqa: E402 (import after dotenv)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger("seed")


def get_client() -> Client:
    """Return a Supabase client authenticated with the service-role key."""
    return create_client(SUPABASE_URL, SERVICE_ROLE_KEY)


# ════════════════════════════════════════════════════════════
# CSV LOADERS
# ════════════════════════════════════════════════════════════

def seed_outlets(client: Client, data_dir: Path) -> int:
    """Seed the outlets table from outlets.csv."""
    csv_path = data_dir / "outlets.csv"
    if not csv_path.exists():
        log.warning("outlets.csv not found at %s — skipping outlets seed", csv_path)
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "outlet_id":           r["outlet_id"],
                "brand":               r["brand"],
                "district":            r["district"],
                "depot":               r["depot"],
                "dock_type":           r["dock_type"],
                "parking_constraint":  r.get("parking_constraint", "normal"),
                "mall_window":         r.get("mall_window") or None,
                "window_open_time":    r["window_open_time"],
                "window_close_time":   r["window_close_time"],
            })

    if rows:
        client.table("outlets").upsert(rows, on_conflict="outlet_id").execute()
        log.info("Seeded %d outlets", len(rows))
    return len(rows)


def seed_vehicles(client: Client, data_dir: Path) -> int:
    """Seed the vehicles table from vehicles.csv."""
    csv_path = data_dir / "vehicles.csv"
    if not csv_path.exists():
        log.warning("vehicles.csv not found at %s — skipping vehicles seed", csv_path)
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "vehicle_id":           r["vehicle_id"],
                "type":                 r["type"],
                "temp":                 r["temp"],
                "weight_cap_kg":        float(r["weight_cap_kg"]),
                "volume_cap_m3":        float(r["volume_cap_m3"]),
                "fuel_type":            r["fuel_type"],
                "km_per_l":             float(r["km_per_l"]),
                "weekly_fuel_quota_l":  float(r["weekly_fuel_quota_l"]),
                "depot":                r["depot"],
            })

    if rows:
        client.table("vehicles").upsert(rows, on_conflict="vehicle_id").execute()
        log.info("Seeded %d vehicles", len(rows))
    return len(rows)


def seed_calendar(client: Client, data_dir: Path) -> int:
    """Seed the calendar table from calendar.csv."""
    csv_path = data_dir / "calendar.csv"
    if not csv_path.exists():
        log.warning("calendar.csv not found at %s — skipping calendar seed", csv_path)
        return 0

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "date":         r["date"],
                "dow":          int(r["dow"]),
                "dow_name":     r["dow_name"],
                "is_weekend":   r["is_weekend"].lower() in ("1", "true", "yes"),
                "iso_year":     int(r["iso_year"]),
                "iso_week":     int(r["iso_week"]),
                "is_payday":    r["is_payday"].lower() in ("1", "true", "yes"),
                "festival":     r.get("festival") or None,
                "festival_ramp": int(float(r["festival_ramp"])) if r.get("festival_ramp") and r["festival_ramp"].strip() else None,
                "is_holiday":   r["is_holiday"].lower() in ("1", "true", "yes"),
                "monsoon":      r["monsoon"].lower() in ("1", "true", "yes"),
                "is_operating": r["is_operating"].lower() in ("1", "true", "yes"),
            })

    # Batch in chunks of 500 to avoid payload limits
    CHUNK = 500
    total = 0
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i + CHUNK]
        client.table("calendar").upsert(chunk, on_conflict="date").execute()
        total += len(chunk)

    log.info("Seeded %d calendar rows", total)
    return total


# ════════════════════════════════════════════════════════════
# DEMO USER ACCOUNTS
# Four seeded accounts — one per role — for the judge walkthrough.
# ════════════════════════════════════════════════════════════

DEMO_USERS = [
    {
        "email":     "storemanager@waypoint.lk",
        "password":  "waypoint123",
        "full_name": "Nimal Fernando",
        "role":      "store_manager",
        "outlet_id": "OUT001",
        "depot":     None,
        "vehicle_id": None,
    },
    {
        "email":     "dispatcher@waypoint.lk",
        "password":  "waypoint123",
        "full_name": "Sunil Jayawardena",
        "role":      "dispatcher",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": None,
    },
    {
        "email":     "loader@waypoint.lk",
        "password":  "waypoint123",
        "full_name": "Kamal Perera",
        "role":      "loader",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": None,
    },
    {
        "email":     "driver@waypoint.lk",
        "password":  "waypoint123",
        "full_name": "Ruwan Silva",
        "role":      "driver",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": "VEH035",
    },
    {
        "email":     "manager@waypoint.demo",
        "password":  "waypoint123",
        "full_name": "Store Manager Kumari",
        "role":      "store_manager",
        "outlet_id": "OUT001",
        "depot":     None,
        "vehicle_id": None,
    },
    {
        "email":     "dispatcher@waypoint.demo",
        "password":  "waypoint123",
        "full_name": "Dispatcher Perera",
        "role":      "dispatcher",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": None,
    },
    {
        "email":     "loader@waypoint.demo",
        "password":  "waypoint123",
        "full_name": "Loader Nimal",
        "role":      "loader",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": None,
    },
    {
        "email":     "driver@waypoint.demo",
        "password":  "waypoint123",
        "full_name": "Rohan Silva",
        "role":      "driver",
        "depot":     "Peliyagoda",
        "outlet_id": None,
        "vehicle_id": "VEH035",
    },
]


def seed_users(client: Client) -> int:
    """
    Create demo Supabase Auth users and corresponding users table rows.
    Uses upsert so re-running is idempotent.

    Note: Supabase Admin API is required to create auth users server-side.
    """
    created = 0
    users_list = []
    try:
        users_list = client.auth.admin.list_users()
    except Exception as e:
        log.warning("Could not list auth users: %s", e)

    for u in DEMO_USERS:
        auth_user_id = None
        existing_auth = next((x for x in users_list if x.email == u["email"]), None)
        if existing_auth:
            auth_user_id = existing_auth.id
            try:
                client.auth.admin.update_user_by_id(auth_user_id, {
                    "password": u["password"],
                    "email_confirm": True,
                })
                log.info("Updated password for auth user: %s (%s)", u["email"], auth_user_id)
            except Exception as e:
                log.warning("Could not update auth user password for %s: %s", u["email"], e)
        else:
            # 1. Create Supabase Auth user
            try:
                auth_response = client.auth.admin.create_user({
                    "email": u["email"],
                    "password": u["password"],
                    "email_confirm": True,  # skip email verification for demo
                    "user_metadata": {"full_name": u["full_name"]},
                })
                auth_user_id = auth_response.user.id
                log.info("Auth user created: %s (%s)", u["email"], auth_user_id)
            except Exception as e:
                log.warning("Could not create auth user %s: %s", u["email"], e)
                existing = client.table("users").select("id").eq("email", u["email"]).maybe_single().execute()
                if existing.data:
                    auth_user_id = existing.data["id"]
                    log.info("Found existing user in table: %s (%s)", u["email"], auth_user_id)
                else:
                    log.error("Cannot create or find user %s — skipping", u["email"])
                    continue

        # 2. Upsert application user profile
        profile = {
            "id":         auth_user_id,
            "email":      u["email"],
            "full_name":  u["full_name"],
            "role":       u["role"],
            "outlet_id":  u.get("outlet_id"),
            "depot":      u.get("depot"),
            "vehicle_id": u.get("vehicle_id"),
            "is_active":   True,
        }
        client.table("users").upsert(profile, on_conflict="id").execute()
        log.info("User profile upserted: %s [%s]", u["full_name"], u["role"])
        created += 1

    return created



# ════════════════════════════════════════════════════════════
# SAMPLE ORDERS (for judge walkthrough day)
# ════════════════════════════════════════════════════════════

def seed_sample_orders(client: Client, plan_date: str = "2026-10-03") -> int:
    """
    Seed a realistic set of orders for the judge walkthrough day.
    These are synthetic orders — not from the competition CSV data.
    """
    # Get some outlet IDs to reference
    outlets_resp = client.table("outlets").select("outlet_id,brand").limit(10).execute()
    if not outlets_resp.data:
        log.warning("No outlets found — run outlet seed first")
        return 0

    # Get dispatcher user ID (may be None if users not seeded yet)
    try:
        dispatcher_resp = client.table("users").select("id").eq("role", "dispatcher").maybe_single().execute()
        created_by = dispatcher_resp.data["id"] if dispatcher_resp and dispatcher_resp.data else None
    except Exception:
        created_by = None

    sample_orders = [
        {
            "outlet_id":        "OUT001",   # Fresh · Colombo
            "brand":            "Fresh",
            "requested_date":   plan_date,
            "status":           "submitted",
            "temp_requirement": "chilled",
            "total_weight_kg":  310.0,
            "total_volume_m3":  1.2,
            "notes":            "Priority — refrigerated goods",
            "created_by":       created_by,
            "submitted_at":     f"{plan_date}T00:00:00+05:30",
        },
        {
            "outlet_id":        "OUT002",   # Fresh · Colombo
            "brand":            "Fresh",
            "requested_date":   plan_date,
            "status":           "submitted",
            "temp_requirement": "ambient",
            "total_weight_kg":  180.0,
            "total_volume_m3":  0.8,
            "notes":            None,
            "created_by":       created_by,
            "submitted_at":     f"{plan_date}T00:00:00+05:30",
        },
        {
            "outlet_id":        "OUT015",   # Style · Colombo
            "brand":            "Style",
            "requested_date":   plan_date,
            "status":           "submitted",
            "temp_requirement": "ambient",
            "total_weight_kg":  90.0,
            "total_volume_m3":  2.1,
            "notes":            "Mall delivery window — check access",
            "created_by":       created_by,
            "submitted_at":     f"{plan_date}T00:00:00+05:30",
        },
        {
            "outlet_id":        "OUT021",   # Tech · Colombo
            "brand":            "Tech",
            "requested_date":   plan_date,
            "status":           "submitted",
            "temp_requirement": "ambient",
            "total_weight_kg":  260.0,
            "total_volume_m3":  0.4,
            "notes":            "High-value — signature required",
            "created_by":       created_by,
            "submitted_at":     f"{plan_date}T00:00:00+05:30",
        },
    ]

    result = client.table("orders").upsert(sample_orders).execute()
    count = len(result.data) if result.data else 0
    log.info("Seeded %d sample orders for %s", count, plan_date)
    return count


# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Waypoint database seed script")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=_REPO_ROOT / "data" / "data" / "General Data",
        help="Directory containing outlets.csv, vehicles.csv, calendar.csv",
    )
    parser.add_argument(
        "--skip-csv",
        action="store_true",
        help="Skip CSV seeding (useful if CSVs not available)",
    )
    parser.add_argument(
        "--skip-users",
        action="store_true",
        help="Skip demo user creation",
    )
    parser.add_argument(
        "--plan-date",
        default="2026-10-03",
        help="Date to use for sample orders (YYYY-MM-DD)",
    )
    args = parser.parse_args()

    log.info("Connecting to Supabase: %s", SUPABASE_URL)
    client = get_client()

    totals: dict[str, int] = {}

    if not args.skip_csv:
        log.info("Seeding reference data from %s", args.data_dir)
        totals["outlets"]  = seed_outlets(client, args.data_dir)
        totals["vehicles"] = seed_vehicles(client, args.data_dir)
        totals["calendar"] = seed_calendar(client, args.data_dir)

    if not args.skip_users:
        log.info("Creating demo user accounts...")
        totals["users"] = seed_users(client)

    log.info("Seeding sample orders for judge walkthrough...")
    totals["orders"] = seed_sample_orders(client, args.plan_date)

    log.info("=" * 50)
    log.info("Seed complete:")
    for k, v in totals.items():
        log.info("  %-12s %d rows", k, v)
    log.info("=" * 50)

    log.info("\nDemo credentials (for judge walkthrough):")
    for u in DEMO_USERS:
        log.info("  [%-14s] %s  /  %s", u["role"], u["email"], u["password"])


if __name__ == "__main__":
    main()
