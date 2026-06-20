import os
from supabase import create_client, Client
import pandas as pd

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
            print(f"Error: {e}")
            break
    return all_data

sm_job_data = get_all_rows('sm_job', 'sm_id, center_name, job_title')
chat_logs_data = get_all_rows('chat_logs', 'userNo, userAction')

df_sm = pd.DataFrame(sm_job_data)
df_chat = pd.DataFrame(chat_logs_data)

print("Unique userActions:", df_chat['userAction'].unique())
print("Total chat logs:", len(df_chat))
print("Questions in chat logs:", len(df_chat[df_chat['userAction'] == 'question']))

merged = pd.merge(df_chat, df_sm, left_on='userNo', right_on='sm_id', how='inner')
print("Total inner joins:", len(merged))

merged_q = merged[merged['userAction'] == 'question']
print("Inner joins that are questions:", len(merged_q))

merged_q_job = merged[(merged['userAction'] == 'question') & (merged['job_title'] == '출장')]
print("Inner joins that are questions and job_title='출장':", len(merged_q_job))

if len(merged_q_job) == 0:
    print("Zero numerator! Checking unique job_titles in sm_job:", df_sm['job_title'].unique())

