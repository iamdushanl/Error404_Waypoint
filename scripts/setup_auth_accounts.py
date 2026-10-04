import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env")
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")
service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

print(f"Connecting to Supabase Admin at {url}...")
admin_client = create_client(url, service_key)

accounts = [
    {
        "email": "storemanager@waypoint.lk",
        "password": "waypoint123",
        "role": "store_manager",
        "name": "Nimal Fernando",
        "outlet_id": "OUT001",
        "depot": None,
    },
    {
        "email": "dispatcher@waypoint.lk",
        "password": "waypoint123",
        "role": "dispatcher",
        "name": "Sunil Jayawardena",
        "outlet_id": None,
        "depot": "Peliyagoda",
    },
    {
        "email": "loader@waypoint.lk",
        "password": "waypoint123",
        "role": "loader",
        "name": "Kamal Perera",
        "outlet_id": None,
        "depot": "Peliyagoda",
    },
    {
        "email": "driver@waypoint.lk",
        "password": "waypoint123",
        "role": "driver",
        "name": "Ruwan Silva",
        "outlet_id": None,
        "depot": "Peliyagoda",
        "vehicle_id": "VEH035",
    },

]

users_list = admin_client.auth.admin.list_users()

for acc in accounts:
    email = acc["email"]
    existing = next((u for u in users_list if u.email == email), None)
    if existing:
        print(f"Updating existing user {email} (ID: {existing.id})...")
        try:
            admin_client.auth.admin.update_user_by_id(
                existing.id,
                {"password": acc["password"], "email_confirm": True}
            )
            uid = existing.id
            print(f"Updated password for {email}")
        except Exception as e:
            print(f"Failed to update user {email}: {e}")
            continue
    else:
        print(f"Creating new auth user {email}...")
        try:
            res = admin_client.auth.admin.create_user({
                "email": email,
                "password": acc["password"],
                "email_confirm": True,
                "user_metadata": {"full_name": acc["name"]}
            })
            uid = res.user.id
            print(f"Created {email} with ID: {uid}")
        except Exception as e:
            print(f"Failed to create user {email}: {e}")
            continue

    # Ensure profile in public.users
    profile = {
        "id": uid,
        "email": email,
        "full_name": acc["name"],
        "role": acc["role"],
        "outlet_id": acc["outlet_id"],
        "depot": acc["depot"],
        "is_active": True,
    }
    try:
        admin_client.table("users").upsert(profile, on_conflict="id").execute()
        print(f"Upserted profile for {email}")
    except Exception as e:
        print(f"Failed to upsert profile for {email}: {e}")

print("\n--- Verifying logins with Supabase Anon Key ---")
anon_client = create_client(url, key)
for acc in accounts:
    email = acc["email"]
    try:
        res = anon_client.auth.sign_in_with_password({
            "email": email,
            "password": acc["password"],
        })
        print(f"[PASS] Successfully signed in as {email} (UID: {res.user.id})")
    except Exception as e:
        print(f"[FAIL] Sign in failed for {email}: {e}")
