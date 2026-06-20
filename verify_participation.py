"""
참여율 계산 검증 스크립트
- 분자: 해당 월/주에 챗봇에 QUESTION을 보낸 고유 사용자 수 (sm_svclist 기준 실근무자만)
- 분모: sm_svclist에서 해당 월에 실제 근무 기록이 있는 고유 사용자 수
- 참여율 = 분자 / 분모 × 100
"""
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
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < limit:
            break
        offset += limit
    return all_data

# 1. sm_svclist 데이터 로드 (분모: 실 근무 인원)
print("sm_svclist 로드 중...")
svclist_data = get_all_rows('sm_svclist', '*')
df_svc = pd.DataFrame(svclist_data)
print(f"  → {len(df_svc)}건 로드 완료")
print(f"  → 컬럼: {list(df_svc.columns)[:10]}")
print(f"  → process_ym 유니크 값: {df_svc['process_ym'].unique()}")
print()

# 2. 5월 데이터만 추출하여 월별 분모 산출
df_svc_may = df_svc[df_svc['process_ym'].astype(str) == '202605'].copy()
df_svc_may['center_short'] = df_svc_may['center_name'].astype(str).str.replace('서비스센터', '').str.strip()
denom_may = df_svc_may.groupby('center_short')['sm_id'].nunique().reset_index(name='denom_users')
print(f"[5월 분모] 센터별 근무 인원 수 (상위 10개):")
print(denom_may.sort_values('denom_users', ascending=False).head(10).to_string(index=False))
print()

# 3. chat_logs에서 5월 QUESTION 로그만 수집 (분자)
print("5월 chat_logs(QUESTION) 로드 중...")
all_chat = []
offset = 0
limit = 1000
while True:
    res = supabase.table('chat_logs').select('userNo, userAction, chatDate, userDeptName').gte('chatDate', '2026-05-01').lt('chatDate', '2026-06-01').range(offset, offset + limit - 1).execute()
    if not res.data:
        break
    all_chat.extend(res.data)
    if len(res.data) < limit:
        break
    offset += limit
df_chat = pd.DataFrame(all_chat)
print(f"  → {len(df_chat)}건 로드 완료")

holidays_to_exclude = ['2026-05-01', '2026-05-05', '2026-05-25']
df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
df_chat = df_chat[
    (df_chat['chatDate_dt'].dt.dayofweek < 5) &
    (~df_chat['chatDate'].isin(holidays_to_exclude))
]
print(f"  → 공휴일/주말 제외 후: {len(df_chat)}건")
print()

# 분자: sm_svclist에 있는 사람만 (실 근무자 필터)
valid_sm_ids = df_svc_may['sm_id'].unique()
q_chat = df_chat[df_chat['userAction'].str.upper() == 'QUESTION'].copy()
q_chat = q_chat[q_chat['userNo'].isin(valid_sm_ids)]
q_chat['dept_short'] = q_chat['userDeptName'].astype(str).str.replace('서비스센터', '').str.strip()

num_may = q_chat.groupby('dept_short')['userNo'].nunique().reset_index(name='num_users')
print(f"[5월 분자] 센터별 QUESTION 발신자 수 (상위 10개):")
print(num_may.sort_values('num_users', ascending=False).head(10).to_string(index=False))
print()

# 4. 분자 / 분모 합산 → 참여율 계산
part = pd.merge(denom_may, num_may, left_on='center_short', right_on='dept_short', how='left')
part['num_users'] = part['num_users'].fillna(0)
part['participation_rate'] = (part['num_users'] / part['denom_users']) * 100

print("[5월 참여율 계산 결과] 전체:")
print(part[['center_short', 'denom_users', 'num_users', 'participation_rate']].sort_values('participation_rate', ascending=False).to_string(index=False))
print()

# 5. 합계 검증
total_denom = part['denom_users'].sum()
total_num = part['num_users'].sum()
print(f"[검증] 5월 총 분모(근무인원 합계): {int(total_denom)}")
print(f"[검증] 5월 총 분자(검색인원 합계): {int(total_num)}")
print(f"[검증] 전체 참여율 평균: {part['participation_rate'].mean():.1f}%")
print(f"[검증] 전체 참여율 중앙값: {part['participation_rate'].median():.1f}%")
print()

# 6. 이상한 케이스 탐지 (100% 초과 등)
over_100 = part[part['participation_rate'] > 100]
if len(over_100) > 0:
    print(f"[경고] 참여율 100% 초과 센터 {len(over_100)}개:")
    print(over_100[['center_short', 'denom_users', 'num_users', 'participation_rate']].to_string(index=False))
else:
    print("[정상] 참여율 100% 초과 센터 없음 (OK)")

zero_rate = part[part['participation_rate'] == 0]
print(f"[참고] 참여율 0% 센터: {len(zero_rate)}개 (분자가 0 = 해당 월에 챗봇 미사용)")
