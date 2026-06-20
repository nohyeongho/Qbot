import os
from supabase import create_client, Client
import pandas as pd
import datetime

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

def get_all_rows(table_name, columns='*'):
    all_data = []
    offset = 0
    limit = 1000
    while True:
        try:
            res = supabase.table(table_name).select(columns).range(offset, offset + limit - 1).execute()
            if not res.data:
                break
            all_data.extend(res.data)
            if len(res.data) < limit:
                break
            offset += limit
        except Exception as e:
            print(f"Error fetching {table_name}: {e}")
            break
    return all_data

sm_job_data = get_all_rows('sm_job', 'sm_id, center_name, job_title')
chat_logs_data = get_all_rows('chat_logs', 'userNo, userAction, chatDate')

df_sm = pd.DataFrame(sm_job_data)
df_chat = pd.DataFrame(chat_logs_data)

holidays_to_exclude = ['2026-05-01', '2026-05-05', '2026-05-25']
df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
df_chat = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) & 
    (~df_chat['chatDate'].isin(holidays_to_exclude))
]

df_chat['iso_week'] = df_chat['chatDate_dt'].dt.isocalendar().week
weeks_in_chat = df_chat['iso_week'].dropna().unique()
print("weeks_in_chat:", weeks_in_chat)
