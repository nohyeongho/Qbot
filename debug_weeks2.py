"""
weekly_center_metrics 딕셔너리의 실제 키 값 확인
- 어떤 센터에, 어떤 주차에, 어떤 값이 들어있는지
"""
import pandas as pd
from supabase import create_client, Client

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

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

holidays_to_exclude = ['2026-05-01', '2026-05-05', '2026-05-25']

sm_data = get_all_rows('sm_job', 'sm_id, center_name, job_title')
chat_data = get_all_rows('chat_logs', 'userNo, userAction, chatDate')

df_sm = pd.DataFrame(sm_data)
df_chat = pd.DataFrame(chat_data)

df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
df_chat = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) &
    (~df_chat['chatDate'].isin(holidays_to_exclude))
]
df_chat['iso_week'] = df_chat['chatDate_dt'].dt.isocalendar().week

import datetime
def get_working_days_for_week(year, week, exclude_holidays):
    d = datetime.date.fromisocalendar(year, week, 1)
    days = 0
    for i in range(5):
        dt = d + datetime.timedelta(days=i)
        if dt.strftime('%Y-%m-%d') not in exclude_holidays:
            days += 1
    return days

weeks_in_chat = df_chat['iso_week'].dropna().unique()
working_days_per_week = {int(w): get_working_days_for_week(2026, int(w), holidays_to_exclude) for w in weeks_in_chat}

merged_w = pd.merge(df_chat, df_sm, left_on='userNo', right_on='sm_id', how='inner')
num_w_df = merged_w[(merged_w['userAction'] == 'QUESTION') & (merged_w['job_title'] == '출장')].groupby(['center_name', 'iso_week']).size().reset_index(name='num')

base_denom_df = df_sm[df_sm['job_title'] == '출장'].groupby('center_name').size().reset_index(name='base_denom')
weekly_metric_df = pd.merge(num_w_df, base_denom_df, on='center_name', how='left')

weekly_metric_df['working_days'] = weekly_metric_df['iso_week'].map(working_days_per_week)
weekly_metric_df['denom'] = weekly_metric_df['base_denom'] * weekly_metric_df['working_days']
weekly_metric_df.loc[weekly_metric_df['denom'] == 0, 'denom'] = 1
weekly_metric_df['인당검색건'] = weekly_metric_df['num'] / weekly_metric_df['denom']

print("=== weekly_metric_df 샘플 (처음 20개) ===")
print(weekly_metric_df[['center_name', 'iso_week', 'num', 'denom', '인당검색건']].head(20).to_string())

print("\n=== 존재하는 iso_week 목록 ===")
print(sorted(weekly_metric_df['iso_week'].unique().astype(int)))

print("\n=== 첫 번째 센터의 주차별 데이터 ===")
first_center = weekly_metric_df['center_name'].iloc[0]
print(f"센터: {first_center}")
print(weekly_metric_df[weekly_metric_df['center_name'] == first_center][['iso_week', '인당검색건']])

# 엑셀에서 실제 센터명 확인
trend_df = pd.read_excel('01_Qbot trend.xlsx', header=None)
excel_centers = []
for r_idx in range(4, len(trend_df)):
    center_name = trend_df.iloc[r_idx, 3]
    if pd.notna(center_name):
        excel_centers.append(str(center_name).strip())

print(f"\n=== 엑셀 센터명 목록 (처음 5개) ===")
print(excel_centers[:5])

print("\n=== 엑셀 센터 중 weekly_center_metrics에 있는 것 ===")
weekly_center_metrics = {}
for _, row in weekly_metric_df.iterrows():
    c_name = str(row['center_name']).strip()
    w = int(row['iso_week'])
    if c_name not in weekly_center_metrics:
        weekly_center_metrics[c_name] = {}
    weekly_center_metrics[c_name][w] = row['인당검색건']

match_count = 0
for ec in set(excel_centers):
    if ec in weekly_center_metrics:
        print(f"  ✓ '{ec}': 주차 {sorted(weekly_center_metrics[ec].keys())}")
        match_count += 1
print(f"매칭된 센터 수: {match_count}")
