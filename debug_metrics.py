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

# Just fetch May data to be fast
res = supabase.table('chat_logs').select('userNo, userAction, chatDate, userDeptName').gte('chatDate', '2026-05-01').lt('chatDate', '2026-06-01').execute()
df_chat = pd.DataFrame(res.data)

holidays_to_exclude = [
    '2026-05-01', '2026-05-05', '2026-05-25'
]

df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'])
df_chat = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) &
    (~df_chat['chatDate'].isin(holidays_to_exclude))
]

merged = pd.merge(df_chat, df_sm, left_on='userNo', right_on='sm_id', how='inner')
num_df = merged[(merged['userAction'] == 'QUESTION') & (merged['job_title'] == '출장')].groupby('center_name').size().reset_index(name='num')

base_denom_df = df_sm[df_sm['job_title'] == '출장'].groupby('center_name').size().reset_index(name='base_denom')
metric = pd.merge(num_df, base_denom_df, on='center_name', how='left')

working_days = 18  # May 2026 working days
metric['denom'] = metric['base_denom'] * working_days
metric['인당검색건'] = metric['num'] / metric['denom']

print(metric.head(10))

# Try calculating it differently: using sm_svclist for denominator
svclist = supabase.table('sm_svclist').select('*').eq('process_ym', '202605').execute()
df_svc = pd.DataFrame(svclist.data)

id_vars = ['sm_id', 'center_name']
day_cols = [f'day_{i:02d}' for i in range(1, 32)]
value_vars = [col for col in day_cols if col in df_svc.columns]
df_long = df_svc.melt(id_vars=id_vars, value_vars=value_vars, var_name='day_col', value_name='work_val')
df_long['work_val'] = pd.to_numeric(df_long['work_val'], errors='coerce').fillna(0)

# 1 이상인 사람(출근한 사람)의 수 총합 (=총 실제 근무일수)
denom_svc = df_long[df_long['work_val'] >= 1].groupby('center_name').size().reset_index(name='real_working_days')

metric_svc = pd.merge(num_df, denom_svc, on='center_name', how='left')
metric_svc['인당검색건_svc'] = metric_svc['num'] / metric_svc['real_working_days']
print("\nUsing sm_svclist:")
print(metric_svc.head(10))
