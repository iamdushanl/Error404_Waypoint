"""
Run migration 004 against Supabase Postgres via psycopg2.
Usage: python scripts/run_migration_004.py
"""
import os
import sys

# Load .env from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, ".env")

# Manual .env parsing (avoid dotenv dependency at script level)
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

DATABASE_URL = env_vars.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env")
    sys.exit(1)

# Read migration file
migration_path = os.path.join(project_root, "supabase", "migrations", "004_allocation_engine_updates.sql")
with open(migration_path) as f:
    sql = f.read()

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

print("Connecting to Supabase Postgres...")
print(f"Host: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'unknown'}")

try:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=20, sslmode="require")
    conn.autocommit = True
    cur = conn.cursor()

    print("Executing migration 004_allocation_engine_updates.sql ...")
    cur.execute(sql)
    print("✅  Migration executed successfully.\n")

    # Verify the new constraint exists
    cur.execute("""
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conname = 'deferred_orders_reason_code_check'
          AND conrelid = 'public.deferred_orders'::regclass
    """)
    row = cur.fetchone()
    if row:
        print("Constraint confirmed:")
        print(row[0])
    else:
        print("WARNING: Constraint not found after migration.")

    # Verify the trips.depot column
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'trips' AND column_name = 'depot'
    """)
    depot_row = cur.fetchone()
    if depot_row:
        print(f"\ntrips.depot column: {depot_row}")
    else:
        print("\nWARNING: trips.depot column not found.")

    cur.close()
    conn.close()
    print("\nDone.")

except psycopg2.OperationalError as e:
    print(f"CONNECTION ERROR: {e}")
    print("\nTip: The Supabase direct connection (port 5432) may be blocked by your network.")
    print("Try running the migration via the Supabase Dashboard SQL Editor instead.")
    sys.exit(1)
except psycopg2.Error as e:
    print(f"SQL ERROR: {e}")
    sys.exit(1)
