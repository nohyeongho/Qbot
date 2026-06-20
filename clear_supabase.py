import time
from supabase import create_client

url: str = "https://seanzwnadqaneusqeami.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase = create_client(url, key)

print("Starting deletion...")
deleted = 0
while True:
    try:
        res = supabase.table("chat_logs").select("id").limit(5000).execute()
        if not res.data:
            break
        ids = [r['id'] for r in res.data]
        # delete by ids
        supabase.table("chat_logs").delete().in_("id", ids).execute()
        deleted += len(ids)
        print(f"Deleted {deleted} rows so far...")
    except Exception as e:
        print(f"Timeout or error, retrying... {e}")
        time.sleep(1)

print("Done.")
