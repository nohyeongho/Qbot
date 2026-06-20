"""
Supabase에서 실제로 데이터가 존재하는 iso_week를 확인하는 디버그 스크립트
"""
import pandas as pd
from supabase import create_client, Client

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

# 전체 chat_logs 가져오기
all_data = []
offset = 0
limit = 1000
while True:
    res = supabase.table('chat_logs').select('chatDate').range(offset, offset + limit - 1).execute()
    if not res.data:
        break
    all_data.extend(res.data)
    if len(res.data) < limit:
        break
    offset += limit

df = pd.DataFrame(all_data)
df['chatDate_dt'] = pd.to_datetime(df['chatDate'], errors='coerce')
df = df[df['chatDate_dt'].dt.dayofweek < 5]  # 평일만

df['iso_week'] = df['chatDate_dt'].dt.isocalendar().week

# 실제 존재하는 주차 출력
weeks = sorted(df['iso_week'].dropna().unique().astype(int))
print(f"데이터가 있는 ISO 주차: {weeks}")
print(f"첫 번째 주차: W{weeks[0]}, 마지막 주차: W{weeks[-1]}")
print(f"전체 행 수: {len(df)}")
