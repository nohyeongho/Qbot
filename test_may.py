import pandas as pd
from supabase import create_client

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase = create_client(url, key)

print("svclist unique process_ym:", supabase.table('sm_svclist').select('process_ym').limit(100).execute().data)

chat = supabase.table('chat_logs').select('chatDate').limit(100).execute().data
print("chat_logs chatDate limit 5:", chat[:5])

# Also let's run update_index.py's participation logic to see what gets stored for month 5
