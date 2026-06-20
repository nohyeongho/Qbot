import os
from supabase import create_client, Client
import pandas as pd

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

all_data = []
offset = 0
limit = 1000
while True:
    res = supabase.table('sm_job').select('center_name', 'job_title').range(offset, offset + limit - 1).execute()
    if not res.data:
        break
    all_data.extend(res.data)
    if len(res.data) < limit:
        break
    offset += limit

df = pd.DataFrame(all_data)
result = df[df['job_title'] == '출장'].groupby('center_name').size()
print(result.to_string())
