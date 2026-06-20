"""
주간 참여율 검증 스크립트 (수정된 로직 적용)
- 수정 1: 분모에서 주말(토/일) 제외
- 수정 2: 분자 = "해당 주에 실제 출근한 사번"과 chat_logs inner join
          (기존: 전체 sm_svclist 등록자 → 100% 초과 버그 원인)
"""
import sys
import io
import pandas as pd
from supabase import create_client

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

url = "https://seanzwnadqaneusqeami.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase = create_client(url, key)

holidays_to_exclude = [
    '2026-01-01', '2026-01-28', '2026-01-29', '2026-01-30',
    '2026-03-01', '2026-05-01', '2026-05-05', '2026-05-25',
    '2026-06-06', '2026-08-15',
    '2026-09-17', '2026-09-18', '2026-09-19',
    '2026-10-03', '2026-10-09', '2026-12-25',
]

def get_all_rows(table_name, columns='*'):
    all_data = []
    offset = 0
    limit = 1000
    while True:
        res = supabase.table(table_name).select(columns).range(offset, offset + limit - 1).execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
    return all_data

# ─────────────────────────────────────────
# 1. 데이터 로드
# ─────────────────────────────────────────
print("sm_svclist 로드 중...")
svclist_data = get_all_rows('sm_svclist', '*')
df_svc = pd.DataFrame(svclist_data)
print(f"  → {len(df_svc)}건 로드 완료")

print("chat_logs 로드 중 (5월, QUESTION 주말/공휴일 제외)...")
all_chat = []
offset = 0
limit = 1000
while True:
    res = supabase.table('chat_logs').select(
        'userNo, userAction, chatDate, userDeptName'
    ).gte('chatDate', '2026-05-01').lt('chatDate', '2026-06-01').range(offset, offset + limit - 1).execute()
    if not res.data:
        break
    all_chat.extend(res.data)
    if len(res.data) < limit:
        break
    offset += limit

df_chat = pd.DataFrame(all_chat)
df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
# 분자용 공휴일/주말 제외
df_chat_weekday = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) &
    (~df_chat['chatDate'].isin(holidays_to_exclude))
].copy()
df_chat_weekday['iso_week'] = df_chat_weekday['chatDate_dt'].dt.isocalendar().week
print(f"  → {len(df_chat)}건 로드 → 주말/공휴일 제외 후: {len(df_chat_weekday)}건\n")

# ─────────────────────────────────────────
# 2. 분모: 주말 제외 + 주차별 출근자
# ─────────────────────────────────────────
df_svc['center_short'] = df_svc['center_name'].astype(str).str.replace('서비스센터', '').str.strip()

day_cols = [f'day_{i:02d}' for i in range(1, 32)]
value_vars = [col for col in day_cols if col in df_svc.columns]

df_long = df_svc.melt(
    id_vars=['sm_id', 'center_name', 'center_short', 'process_ym'],
    value_vars=value_vars, var_name='day_col', value_name='work_val'
)
df_long['work_val'] = pd.to_numeric(df_long['work_val'], errors='coerce').fillna(0)
df_active = df_long[df_long['work_val'] >= 1].copy()

# 날짜 변환
df_active['day_num'] = df_active['day_col'].str.replace('day_', '')
df_active['process_ym_str'] = (
    pd.to_numeric(df_active['process_ym'], errors='coerce').fillna(0).astype(int).astype(str)
)
df_active['date_str'] = df_active['process_ym_str'] + df_active['day_num']
df_active['date_dt'] = pd.to_datetime(df_active['date_str'], format='%Y%m%d', errors='coerce')
df_active = df_active.dropna(subset=['date_dt'])
df_active['iso_week'] = df_active['date_dt'].dt.isocalendar().week

# [수정] 주말 제외
df_active = df_active[df_active['date_dt'].dt.dayofweek < 5].copy()
print(f"[분모] 주말 제거 후 출근 레코드: {len(df_active)}건")

# 분모 후보 집합: (center_short, iso_week, sm_id)
denom_pool = df_active[['center_short', 'iso_week', 'sm_id']].drop_duplicates()
denom_w_df = denom_pool.groupby(['center_short', 'iso_week'])['sm_id'].nunique().reset_index(name='denom_users')

# ─────────────────────────────────────────
# 3. 분자: 해당 주 출근자와 inner join
# ─────────────────────────────────────────
q_chat_w = df_chat_weekday[
    df_chat_weekday['userAction'].astype(str).str.upper() == 'QUESTION'
].copy()

# [핵심 수정] 전체 sm_svclist 사번이 아닌, 해당 주에 출근한 사번으로만 필터
q_merged_w = pd.merge(
    q_chat_w[['userNo', 'iso_week']].rename(columns={'userNo': 'sm_id'}),
    denom_pool,             # (center_short, iso_week, sm_id)
    on=['sm_id', 'iso_week'],
    how='inner'             # 해당 주 출근자의 채팅만 인정
)
num_w_df = q_merged_w.groupby(['center_short', 'iso_week'])['sm_id'].nunique().reset_index(name='num_users')

# ─────────────────────────────────────────
# 4. 참여율 계산
# ─────────────────────────────────────────
part_w = pd.merge(denom_w_df, num_w_df, on=['center_short', 'iso_week'], how='left')
part_w['num_users'] = part_w['num_users'].fillna(0)
part_w['participation_rate'] = 0.0
mask = part_w['denom_users'] > 0
part_w.loc[mask, 'participation_rate'] = (
    part_w.loc[mask, 'num_users'] / part_w.loc[mask, 'denom_users']
) * 100

# ─────────────────────────────────────────
# 5. 결과 출력
# ─────────────────────────────────────────
print("\n" + "=" * 55)
print("[주간 참여율] 주차별 요약")
print("=" * 55)
week_summary = part_w.groupby('iso_week').agg(
    avg_rate=('participation_rate', 'mean'),
    median_rate=('participation_rate', 'median'),
    total_denom=('denom_users', 'sum'),
    total_num=('num_users', 'sum'),
).reset_index()
print(week_summary.to_string(index=False))

print("\n" + "=" * 55)
print("[이상값 탐지]")
print("=" * 55)

over_100 = part_w[part_w['participation_rate'] > 100]
if len(over_100) > 0:
    print(f"[경고] 참여율 100% 초과: {len(over_100)}건")
    print(over_100[['center_short', 'iso_week', 'denom_users', 'num_users', 'participation_rate']].to_string(index=False))
else:
    print("[정상] 참여율 100% 초과 없음 (OK)")

zero_rate = part_w[part_w['participation_rate'] == 0]
print(f"\n[참고] 참여율 0% 케이스: {len(zero_rate)}건")
if len(zero_rate) > 0:
    print(zero_rate[['center_short', 'iso_week', 'denom_users', 'num_users']].head(10).to_string(index=False))

print("\n" + "=" * 55)
print(f"전체 주간 참여율 평균: {part_w['participation_rate'].mean():.1f}%")
print(f"전체 주간 참여율 중앙값: {part_w['participation_rate'].median():.1f}%")
