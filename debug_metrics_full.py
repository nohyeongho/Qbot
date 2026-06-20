import pandas as pd
from supabase import create_client

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase = create_client(url, key)

def get_all_rows(table_name, columns='*'):
    all_data = []
    offset = 0
    limit = 1000
    while True:
        res = supabase.table(table_name).select(columns).range(offset, offset + limit - 1).execute()
        if not res.data: break
        all_data.extend(res.data)
        if len(res.data) < limit: break
        offset += limit
    return all_data

sm_job = get_all_rows('sm_job', 'sm_id, center_name, job_title')
df_sm = pd.DataFrame(sm_job)

# Fetch all chat logs to match update_index.py
chat_logs = get_all_rows('chat_logs', 'userNo, userAction, chatDate, userDeptName')
df_chat = pd.DataFrame(chat_logs)

holidays_to_exclude = [
    '2026-01-01', '2026-01-28', '2026-01-29', '2026-01-30', '2026-03-01', 
    '2026-05-01', '2026-05-05', '2026-05-25', '2026-06-06', '2026-08-15', 
    '2026-09-17', '2026-09-18', '2026-09-19', '2026-10-03', '2026-10-09', '2026-12-25'
]

df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
df_chat = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) &
    (~df_chat['chatDate'].isin(holidays_to_exclude))
]

df_chat['month'] = df_chat['chatDate_dt'].dt.month

# working days for May
working_days_per_month = {5: 18} # Let's assume May only for now

merged_m = pd.merge(df_chat, df_sm, left_on='userNo', right_on='sm_id', how='inner')
num_m_df = merged_m[
    (merged_m['userAction'] == 'QUESTION') & (merged_m['job_title'] == '출장')
].groupby(['center_name', 'month']).size().reset_index(name='num')

base_denom_df_m = df_sm[df_sm['job_title'] == '출장'].groupby('center_name').size().reset_index(name='base_denom')
monthly_metric_df = pd.merge(num_m_df, base_denom_df_m, on='center_name', how='left')
monthly_metric_df['working_days'] = monthly_metric_df['month'].map(working_days_per_month)
monthly_metric_df['denom'] = monthly_metric_df['base_denom'] * monthly_metric_df['working_days']
monthly_metric_df.loc[monthly_metric_df['denom'] == 0, 'denom'] = 1
monthly_metric_df['인당검색건'] = monthly_metric_df['num'] / monthly_metric_df['denom']

print(monthly_metric_df.head(10))
