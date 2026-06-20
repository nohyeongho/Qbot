import pandas as pd
import json
import re
import math
from datetime import datetime
import os
from supabase import create_client, Client

# Supabase 연동 설정
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

def get_working_days_for_week(year, week, exclude_holidays):
    import datetime
    d = datetime.date.fromisocalendar(year, week, 1)
    days = 0
    for i in range(5):
        dt = d + datetime.timedelta(days=i)
        if dt.strftime('%Y-%m-%d') not in exclude_holidays:
            days += 1
    return days

def get_working_days_for_month(year, month, exclude_holidays):
    """주어진 연/월의 실제 근무일수를 동적으로 계산 (월별 자동화를 위해 추가)"""
    import datetime, calendar
    _, last_day = calendar.monthrange(year, month)
    days = 0
    for d in range(1, last_day + 1):
        date = datetime.date(year, month, d)
        if date.weekday() < 5 and date.strftime('%Y-%m-%d') not in exclude_holidays:
            days += 1
    return days

print("Fetching Supabase data for 인당검색건 and 참여율 calculation...")
sm_job_data = get_all_rows('sm_job', 'sm_id, center_name, job_title')
chat_logs_data = get_all_rows('chat_logs', 'userNo, userAction, chatDate, userDeptName')
sm_svclist_data = get_all_rows('sm_svclist', '*')

df_sm = pd.DataFrame(sm_job_data)
df_chat = pd.DataFrame(chat_logs_data)

# 2026년 전체 공휴일 목록 (월별 자동 계산에 사용)
# → 새 데이터를 Supabase에 올리면 이 목록 기준으로 근무일 자동 계산
holidays_to_exclude = [
    '2026-01-01',                                      # 신정
    '2026-01-28', '2026-01-29', '2026-01-30',          # 설날
    '2026-03-01',                                      # 삼일절
    '2026-05-01',                                      # 근로자의 날
    '2026-05-05',                                      # 어린이날
    '2026-05-25',                                      # 부처님오신날
    '2026-06-06',                                      # 현충일
    '2026-08-15',                                      # 광복절
    '2026-09-17', '2026-09-18', '2026-09-19',          # 추석
    '2026-10-03',                                      # 개천절
    '2026-10-09',                                      # 한글날
    '2026-12-25',                                      # 성탄절
]

# 월별 통계 딕셔너리 초기화
monthly_center_metrics = {}

if not df_sm.empty and not df_chat.empty:
    if 'chatDate' in df_chat.columns:
        df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
        # 주말(dayofweek: 5=Sat, 6=Sun) 및 공휴일 필터링 (분자)
        df_chat = df_chat[
            (df_chat['chatDate_dt'].dt.dayofweek < 5) &
            (~df_chat['chatDate'].isin(holidays_to_exclude))
        ]

    # 월별 통계 (Monthly metrics) - 자동으로 모든 월 계산
    # → Supabase에 6월 이후 데이터 올리면 자동 반영
    if 'chatDate_dt' in df_chat.columns:
        df_chat['month'] = df_chat['chatDate_dt'].dt.month
        months_in_chat = df_chat['month'].dropna().unique()
        working_days_per_month = {
            int(m): get_working_days_for_month(2026, int(m), holidays_to_exclude)
            for m in months_in_chat
        }

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

        for _, row in monthly_metric_df.iterrows():
            c_name = str(row['center_name']).replace('서비스센터', '').strip()
            m_key = int(row['month'])
            if c_name not in monthly_center_metrics:
                monthly_center_metrics[c_name] = {}
            monthly_center_metrics[c_name][m_key] = row['인당검색건']

    # ─── 참여율 (Participation Rate) 계산 (월별) ───
    monthly_participation_rate = {}
    if sm_svclist_data and not df_chat.empty and 'chatDate_dt' in df_chat.columns:
        df_svclist = pd.DataFrame(sm_svclist_data)
        if not df_svclist.empty:
            df_svclist['month'] = df_svclist['process_ym'].astype(str).str[-2:].astype(float)
            df_svclist['center_short'] = df_svclist['center_name'].astype(str).str.replace('서비스센터', '').str.strip()
            
            # [B 기준 수정] 단순 등록 인원이 아니라,
            # day_01~day_31 중 하나라도 실제 출근(값 >= 1)한 인원만 분모로 사용.
            # → 등록되었지만 한 번도 출근하지 않은 인원은 분모에서 제외하여 참여율 정확도 향상
            day_cols_m = [f'day_{i:02d}' for i in range(1, 32)]
            value_vars_m = [col for col in day_cols_m if col in df_svclist.columns]
            df_long_m = df_svclist.melt(
                id_vars=['sm_id', 'center_name', 'center_short', 'month'],
                value_vars=value_vars_m,
                var_name='day_col',
                value_name='work_val'
            )
            df_long_m['work_val'] = pd.to_numeric(df_long_m['work_val'], errors='coerce').fillna(0)
            # 1일 이상 근무한 레코드만 필터링
            df_active_m = df_long_m[df_long_m['work_val'] >= 1]
            # 실제 출근한 sm_id만 고유하게 집계 → 분모
            denom_df = df_active_m.groupby(['center_name', 'center_short', 'month'])['sm_id'].nunique().reset_index(name='denom_users')
            
            q_chat = df_chat[df_chat['userAction'].astype(str).str.upper() == 'QUESTION'].copy()
            
            # sm_svclist에 있는 인원(실 근무자)만 분자 대상자로 필터링
            valid_sm_ids = df_svclist['sm_id'].unique()
            q_chat = q_chat[q_chat['userNo'].isin(valid_sm_ids)]
            
            q_chat['dept_short'] = q_chat['userDeptName'].astype(str).str.replace('서비스센터', '').str.strip()
            num_df = q_chat.groupby(['dept_short', 'month'])['userNo'].nunique().reset_index(name='num_users')
            
            part_rate_df = pd.merge(denom_df, num_df, left_on=['center_short', 'month'], right_on=['dept_short', 'month'], how='left')
            part_rate_df['num_users'] = part_rate_df['num_users'].fillna(0)
            
            part_rate_df['participation_rate'] = 0.0
            mask = part_rate_df['denom_users'] > 0
            part_rate_df.loc[mask, 'participation_rate'] = (part_rate_df.loc[mask, 'num_users'] / part_rate_df.loc[mask, 'denom_users']) * 100
            
            for _, row in part_rate_df.iterrows():
                # trend_df의 담당/센터 이름과 맞추기 위해 center_short 사용
                c_name = str(row['center_short']).strip()
                m_key = int(row['month'])
                if c_name not in monthly_participation_rate:
                    monthly_participation_rate[c_name] = {}
                monthly_participation_rate[c_name][m_key] = row['participation_rate']

    # ─── 참여율 (Participation Rate) 계산 (주간) ───
    weekly_participation_rate = {}
    if sm_svclist_data and not df_chat.empty and 'chatDate_dt' in df_chat.columns:
        df_svclist = pd.DataFrame(sm_svclist_data)
        if not df_svclist.empty:
            df_svclist['month'] = df_svclist['process_ym'].astype(str).str[-2:].astype(float)
            df_svclist['center_short'] = df_svclist['center_name'].astype(str).str.replace('서비스센터', '').str.strip()
            
            # 1. 일별 근무 데이터(day_01 ~ day_31)를 Long 형식으로 변환 (melt)
            id_vars = ['sm_id', 'center_name', 'center_short', 'process_ym']
            day_cols = [f'day_{i:02d}' for i in range(1, 32)]
            value_vars = [col for col in day_cols if col in df_svclist.columns]
            
            df_long = df_svclist.melt(id_vars=id_vars, value_vars=value_vars, var_name='day_col', value_name='work_val')
            
            # 2. 근무일수(work_val)가 1 이상인 데이터만 필터링 (결측치/None 방어)
            df_long['work_val'] = pd.to_numeric(df_long['work_val'], errors='coerce').fillna(0)
            df_active = df_long[df_long['work_val'] >= 1].copy()
            
            # 3. YYYYMM + DD 문자열을 결합하여 실제 날짜(Datetime)로 변환
            df_active['day_num'] = df_active['day_col'].str.replace('day_', '')
            df_active['process_ym_str'] = pd.to_numeric(df_active['process_ym'], errors='coerce').fillna(0).astype(int).astype(str)
            df_active['date_str'] = df_active['process_ym_str'] + df_active['day_num']
            df_active['date_dt'] = pd.to_datetime(df_active['date_str'], format='%Y%m%d', errors='coerce')
            df_active = df_active.dropna(subset=['date_dt'])
            
            # 날짜 기반으로 해당 일자의 정확한 주차(ISO Week) 추출
            df_active['iso_week'] = df_active['date_dt'].dt.isocalendar().week

            # [수정] 분모에서 주말(토=5, 일=6) 제외
            # → 분자(chat_logs)도 주말을 제외하므로 기준을 일치시킴
            # → 주말 출근 기록이 분모를 과대계상하는 문제 방지
            df_active = df_active[df_active['date_dt'].dt.dayofweek < 5].copy()

            # 4. 주간 분모(Denominator) 후보 집합 생성: (center_short, iso_week, sm_id)
            # → 이후 분자 계산 시 "해당 주 출근자"로 교차 필터링에 재사용
            denom_pool_w = df_active[['center_short', 'iso_week', 'sm_id']].drop_duplicates()
            denom_w_df = denom_pool_w.groupby(['center_short', 'iso_week'])['sm_id'].nunique().reset_index(name='denom_users')

            # 5. 주간 분자(Numerator) 산출
            q_chat_w = df_chat[df_chat['userAction'].astype(str).str.upper() == 'QUESTION'].copy()
            q_chat_w['iso_week'] = q_chat_w['chatDate_dt'].dt.isocalendar().week

            # [핵심 수정] 분자 필터를 "전체 sm_svclist 등록자" → "해당 주에 실제 출근한 사번"으로 변경
            # 이유: 해당 주에 출근하지 않은 사람도 sm_svclist에 있으면 분자에 포함되어 100% 초과 발생
            # → denom_pool_w와 sm_id + iso_week 기준 inner join → 출근한 주에 사용한 건만 인정
            q_merged_w = pd.merge(
                q_chat_w[['userNo', 'iso_week']].rename(columns={'userNo': 'sm_id'}),
                denom_pool_w,          # (center_short, iso_week, sm_id)
                on=['sm_id', 'iso_week'],
                how='inner'            # 해당 주 출근자의 채팅만 분자로 집계
            )
            num_df_w = q_merged_w.groupby(['center_short', 'iso_week'])['sm_id'].nunique().reset_index(name='num_users')

            # 6. 분모/분자 병합 및 주간 참여율(%) 계산
            # center_short 기준으로 통일 (기존의 dept_short 매핑 불일치 문제도 동시에 해결)
            part_rate_w_df = pd.merge(denom_w_df, num_df_w, on=['center_short', 'iso_week'], how='left')
            part_rate_w_df['num_users'] = part_rate_w_df['num_users'].fillna(0)

            part_rate_w_df['participation_rate'] = 0.0
            mask_w = part_rate_w_df['denom_users'] > 0
            part_rate_w_df.loc[mask_w, 'participation_rate'] = (part_rate_w_df.loc[mask_w, 'num_users'] / part_rate_w_df.loc[mask_w, 'denom_users']) * 100
            
            # 7. 딕셔너리에 저장
            for _, row in part_rate_w_df.iterrows():
                # trend_df의 담당/센터 이름과 맞추기 위해 center_short 사용
                c_name = str(row['center_short']).strip()
                w_key = int(row['iso_week']) if pd.notna(row['iso_week']) else -1
                if w_key != -1:
                    if c_name not in weekly_participation_rate:
                        weekly_participation_rate[c_name] = {}
                    weekly_participation_rate[c_name][w_key] = row['participation_rate']
            print(f"Weekly participation rate calculated for {len(weekly_participation_rate)} centers.")
            if len(weekly_participation_rate) > 0:
                sample_k = list(weekly_participation_rate.keys())[0]
                print(f"Sample weekly rates for {sample_k}: {weekly_participation_rate[sample_k]}")
    
    # 주간 통계 (Weekly metrics)
    weekly_center_metrics = {}
    if 'chatDate_dt' in df_chat.columns:
        df_chat['iso_week'] = df_chat['chatDate_dt'].dt.isocalendar().week
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
        
        for _, row in weekly_metric_df.iterrows():
            c_name = str(row['center_name']).replace('서비스센터', '').strip()
            w = int(row['iso_week'])
            val = row['인당검색건']
            if c_name not in weekly_center_metrics:
                weekly_center_metrics[c_name] = {}
            weekly_center_metrics[c_name][w] = val

print(f"Calculated monthly metrics for {len(monthly_center_metrics)} centers.")

# [메모리 최적화] 전체 데이터를 메모리에 올리면 MemoryError 발생.
# SQLite에서 각 KPI에 필요한 집계 쿼리만 실행하여 결과(소량)만 가져옴.
import sqlite3 as _sqlite3
print("Calculating KPIs from SQLite (dashboard.db)...")
_conn = _sqlite3.connect('dashboard.db')
_cur = _conn.cursor()

# 1. 총 검색 건수
_cur.execute("SELECT COUNT(*) FROM chat_logs")
total_inquiries = _cur.fetchone()[0]

# 2. 총 사용자 수 (동명이인 구분: 이름+사번 조합)
_cur.execute("SELECT COUNT(DISTINCT COALESCE(userName,'') || COALESCE(userNo,'')) FROM chat_logs")
total_users = _cur.fetchone()[0]

# 3. 날짜 범위
_cur.execute("SELECT MIN(chatDate), MAX(chatDate) FROM chat_logs")
_min_date, _max_date = _cur.fetchone()
from datetime import datetime as _dt
start_date = _dt.strptime(_min_date[:10], '%Y-%m-%d').strftime('%Y.%m.%d')
end_date   = _dt.strptime(_max_date[:10], '%Y-%m-%d').strftime('%m.%d')
date_str = f"{start_date} ~ {end_date}"

# 4. 시간대별 분포
_cur.execute("SELECT CAST(SUBSTR(chatHour,1,2) AS INTEGER) as h, COUNT(*) FROM chat_logs GROUP BY h ORDER BY h")
_hour_rows = _cur.fetchall()
hours_label = [str(r[0]).zfill(2) for r in _hour_rows]
hours_data  = [r[1] for r in _hour_rows]

# 5. 질문 유형 도넛
_cur.execute("SELECT questionTypeCd, COUNT(*) FROM chat_logs GROUP BY questionTypeCd")
_type_dict = {r[0]: r[1] for r in _cur.fetchall()}
type_data = [
    int(_type_dict.get('UNIFIED_TECH', 0)),
    int(_type_dict.get('MODEL_SYMPTOM', 0)),
    int(_type_dict.get('SPEC_INFO', 0)),
]
type_data.append(total_inquiries - sum(type_data))

# 6. 상위 사용자 Top 10
_cur.execute("""
    SELECT COALESCE(userName,'알수없음') || '(' || COALESCE(userNo,'알수없음') || ')' AS user_key,
           COUNT(*) AS cnt
    FROM chat_logs
    GROUP BY user_key
    ORDER BY cnt DESC
    LIMIT 10
""")
_user_rows = _cur.fetchall()
user_names = [r[0] for r in _user_rows]
user_vals  = [r[1] for r in _user_rows]

# 7. 센터별 Top 10
_cur.execute("""
    SELECT REPLACE(COALESCE(userDeptName,''), '서비스센터', '') AS center,
           COUNT(*) AS cnt
    FROM chat_logs
    GROUP BY center
    ORDER BY cnt DESC
    LIMIT 10
""")
_center_rows = _cur.fetchall()
centers     = [r[0] for r in _center_rows]
center_vals = [r[1] for r in _center_rows]

# 8. 응답 완결률
_cur.execute("SELECT aiResultStatus, COUNT(*) FROM chat_logs GROUP BY aiResultStatus")
_ai_dict = {r[0]: r[1] for r in _cur.fetchall()}
resolved   = int(_ai_dict.get('SUCCESS', 0))
unresolved = int(_ai_dict.get('FAIL', 0))
_conn.close()
resolve_rate = round(resolved / total_inquiries * 100, 1) if total_inquiries > 0 else 0
print(f"KPI calculated: {total_users}명, {total_inquiries}건")

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace data in index.html using robust regex matching
html = re.sub(r'\d{4}\.\d{2}\.\d{2} ~ \d{2}\.\d{2}', date_str, html)
html = re.sub(r'\d+명 · \d+건', f"{total_users}명 · {total_inquiries}건", html)
html = re.sub(r'(<div class="kpi-val" id="kpi-users">).*?(</div>)', f'\\g<1>{total_users}\\g<2>', html)
html = re.sub(r'(<div class="kpi-val" id="kpi-inquiries">).*?(</div>)', f'\\g<1>{total_inquiries}\\g<2>', html)
html = re.sub(r'\d+ / \d+ 클릭', f"{int(total_inquiries*0.624)} / {total_inquiries} 클릭", html)

# JavaScript cHour Chart (document.getElementById('cHour') 기준으로 매칭)
html = re.sub(r"(document\.getElementById\('cHour'\)[\s\S]*?labels:\s*)\[.*?\]", f"\\g<1>{json.dumps(hours_label)}", html)
html = re.sub(r"(document\.getElementById\('cHour'\)[\s\S]*?data:\s*)\[.*?\]", f"\\g<1>{json.dumps(hours_data)}", html)

# JavaScript cType Chart (document.getElementById('cType') 기준으로 매칭)
html = re.sub(r"(document\.getElementById\('cType'\)[\s\S]*?data:\s*)\[.*?\]", f"\\g<1>{json.dumps(type_data[:3])}", html)

# JavaScript variables for Top Users and Centers
html = re.sub(r"(const names = )\[.*?\];", f"\\g<1>{json.dumps(user_names, ensure_ascii=False)};", html)
html = re.sub(r"(const vals = )\[.*?\];", f"\\g<1>{json.dumps(user_vals)};", html)

html = re.sub(r"(const centers = )\[.*?\];", f"\\g<1>{json.dumps(centers, ensure_ascii=False)};", html)
html = re.sub(r"(const centerVals = )\[.*?\];", f"\\g<1>{json.dumps(center_vals)};", html)

# --- 담당/센터별 현황판 데이터 로드 및 HTML 생성 ---
try:
    print("Loading trend excel...")
    trend_df = pd.read_excel('01_Qbot trend.xlsx', header=None)
    
    trend_html = "<table class='trend-table'>\n"
    trend_html += "  <thead>\n"
    # 첫 3줄(인덱스 1,2,3) 헤더 파싱
    for r_idx in range(1, 4):
        trend_html += "    <tr>\n"
        if r_idx in (1, 2):
            c_idx = 0
            while c_idx < 31:
                val = trend_df.iloc[r_idx, c_idx]
                if pd.isna(val):
                    val = ""
                else:
                    val = str(val).replace('\n', '<br>')
                
                # 고정된 컬럼 레이아웃에 따른 colspan 지정
                if r_idx == 1:
                    if c_idx == 4: 
                        html_colspan = 2
                        excel_skip = 2
                    elif c_idx == 6: 
                        html_colspan = 24 # 1~12월 커버
                        excel_skip = 12
                        val = """
                            <div style="display:flex; justify-content:center; align-items:center; gap:10px;">
                                <span style="cursor:pointer; padding:2px 8px; background:#334155; border-radius:4px; font-size:11px; color:#fff; transition:0.2s;" onmouseover="this.style.background='#475569'" onmouseout="this.style.background='#334155'" onclick="slideMonth(-1)">◀ 이전</span>
                                <span>월간</span>
                                <span style="cursor:pointer; padding:2px 8px; background:#334155; border-radius:4px; font-size:11px; color:#fff; transition:0.2s;" onmouseover="this.style.background='#475569'" onmouseout="this.style.background='#334155'" onclick="slideMonth(1)">다음 ▶</span>
                            </div>
                        """
                        trend_html += f"      <th colspan='{html_colspan}' id='monthly-master-header'>{val}</th>\n"
                        c_idx += excel_skip
                        continue
                    elif c_idx == 18: 
                        html_colspan = 1
                        excel_skip = 1
                    elif c_idx == 19: 
                        html_colspan = 104 # W1~W52 (52주 * 2) 커버
                        excel_skip = 12
                        val = """
                            <div style="display:flex; justify-content:center; align-items:center; gap:10px;">
                                <span style="cursor:pointer; padding:2px 8px; background:#334155; border-radius:4px; font-size:11px; color:#fff; transition:0.2s;" onmouseover="this.style.background='#475569'" onmouseout="this.style.background='#334155'" onclick="slideWeek(-1)">◀ 이전</span>
                                <span>주간</span>
                                <span style="cursor:pointer; padding:2px 8px; background:#334155; border-radius:4px; font-size:11px; color:#fff; transition:0.2s;" onmouseover="this.style.background='#475569'" onmouseout="this.style.background='#334155'" onclick="slideWeek(1)">다음 ▶</span>
                            </div>
                        """
                        trend_html += f"      <th colspan='{html_colspan}' id='weekly-master-header'>{val}</th>\n"
                        c_idx += excel_skip
                        continue
                    else: 
                        html_colspan = 1
                        excel_skip = 1
                elif r_idx == 2:
                    if c_idx in [4, 6, 8, 10, 12, 14, 16]: 
                        html_colspan = 2
                        excel_skip = 2
                    elif c_idx == 18: 
                        html_colspan = 1
                        excel_skip = 1
                    elif c_idx in [19, 21, 23, 25, 27, 29]: 
                        html_colspan = 2
                        excel_skip = 2
                    else: 
                        html_colspan = 1
                        excel_skip = 1
                
                if r_idx == 2 and c_idx in [6, 8, 10, 12, 14, 16]:
                    m = (c_idx - 6) // 2 + 1
                    class_attr = f" class='month-col month-{m}'"
                elif r_idx == 2 and c_idx in [19, 21, 23, 25, 27, 29]:
                    # 실제 ISO 주차 번호를 그대로 사용 (W21~W26)
                    w = 21 + (c_idx - 19) // 2
                    class_attr = f" class='week-col week-{w}'"
                    val = f"W{w}"
                else:
                    class_attr = ""

                # W21(c_idx==19) 출력 직전에 W1~W20 헤더 추가
                # → Supabase에 W18, W19 등 초기 주차 데이터가 있으면 이 컬럼에 표시됨
                if r_idx == 2 and c_idx == 19:
                    for w_ex in range(1, 21):
                        trend_html += f"      <th colspan='2' class='week-col week-{w_ex}'>W{w_ex}</th>\n"

                if html_colspan > 1:
                    trend_html += f"      <th colspan='{html_colspan}'{class_attr}>{val}</th>\n"
                else:
                    trend_html += f"      <th{class_attr}>{val}</th>\n"
                
                # 6월(c_idx==16) 출력 직후 7~12월 추가
                if r_idx == 2 and c_idx == 16:
                    for m in range(7, 13):
                        trend_html += f"      <th colspan='2' class='month-col month-{m}'>{m}월</th>\n"
                        
                # W26(c_idx==29) 출력 직후 W27~W52 추가 (나머지 빈 주차)
                if r_idx == 2 and c_idx == 29:
                    for w in range(27, 53):
                        trend_html += f"      <th colspan='2' class='week-col week-{w}'>W{w}</th>\n"
                        
                c_idx += excel_skip
        else: # r_idx == 3
            for c_idx in range(31):
                val = trend_df.iloc[r_idx, c_idx]
                if pd.isna(val):
                    val = ""
                else:
                    val = str(val).replace('\n', '<br>')
                    
                m = -1
                if 6 <= c_idx <= 17:
                    m = (c_idx - 6) // 2 + 1
                    
                w = -1
                if 19 <= c_idx <= 30:
                    # 실제 ISO 주차 번호 사용 (W21~W26)
                    w = 21 + (c_idx - 19) // 2
                    
                class_attr = ""
                if m != -1:
                    class_attr = f" class='month-col month-{m}'"
                elif w != -1:
                    class_attr = f" class='week-col week-{w}'"

                # W21(c_idx==19) 하위 헤더 직전에 W1~W20 하위 헤더 추가
                # → W18, W19 등 실제 데이터가 있는 주차의 서브 헤더
                if c_idx == 19:
                    for w_ex in range(1, 21):
                        trend_html += f"      <th class='week-col week-{w_ex}'>인당<br>검색건</th>\n"
                        trend_html += f"      <th class='week-col week-{w_ex}'>참여율</th>\n"
                        
                trend_html += f"      <th{class_attr}>{val}</th>\n"
                # 6월 데이터 헤더 직후(c_idx==17) 7~12월 하위 헤더 추가
                if c_idx == 17:
                    for m in range(7, 13):
                        trend_html += f"      <th class='month-col month-{m}'>인당<br>검색건</th>\n"
                        trend_html += f"      <th class='month-col month-{m}'>참여율</th>\n"
                        
                # W26 데이터 헤더 직후(c_idx==30) W27~W52 하위 헤더 추가 (나머지 빈 주차)
                if c_idx == 30:
                    for w in range(27, 53):
                        trend_html += f"      <th class='week-col week-{w}'>인당<br>검색건</th>\n"
                        trend_html += f"      <th class='week-col week-{w}'>참여율</th>\n"
        trend_html += "    </tr>\n"
    trend_html += "  </thead>\n"
    trend_html += "  <tbody>\n"
    
    # 4번째 줄부터 데이터 파싱
    for r_idx in range(4, len(trend_df)):
        # 부문(col 1)과 담당/센터(col 3)가 모두 비어있으면 빈 줄이므로 스킵
        if pd.isna(trend_df.iloc[r_idx, 1]) and pd.isna(trend_df.iloc[r_idx, 3]):
            continue
            
        trend_html += "    <tr>\n"
        for c_idx in range(31):
            val = trend_df.iloc[r_idx, c_idx]
            if pd.isna(val):
                val = ""
            elif isinstance(val, (int, float)):
                # 사용자의 요청에 따라 숫자는 모두 삭제 (빈칸 처리)
                val = ""
            else:
                val = str(val)
                
            # 월간 인당검색건 수치에 Supabase 계산값 주입 (c_idx 6,8,10,12,14,16 → 1~6월)
            # → 6월 이후 데이터도 자동 반영됨
            if 6 <= c_idx <= 16 and (c_idx - 6) % 2 == 0:
                center_name = trend_df.iloc[r_idx, 3]
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    m_key = (c_idx - 6) // 2 + 1  # c_idx→month 매핑 (6→1월, 8→2월...)
                    if c_name in monthly_center_metrics and m_key in monthly_center_metrics[c_name]:
                        val = f"{monthly_center_metrics[c_name][m_key]:.1f}"

            # 월간 참여율 수치에 Supabase 계산값 주입 (c_idx 7,9,11,13,15,17 → 1~6월)
            if 7 <= c_idx <= 17 and (c_idx - 7) % 2 == 0:
                center_name = trend_df.iloc[r_idx, 3]
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    m_key = (c_idx - 7) // 2 + 1
                    if 'monthly_participation_rate' in locals() and c_name in monthly_participation_rate and m_key in monthly_participation_rate[c_name]:
                        rate_val = monthly_participation_rate[c_name][m_key]
                        if rate_val >= 0:
                            val = f"{rate_val:.1f}%"
                        else:
                            val = "-"
                        
            m = -1
            if 6 <= c_idx <= 17:
                m = (c_idx - 6) // 2 + 1
                
            w = -1
            if 19 <= c_idx <= 30:
                # 실제 ISO 주차 번호 사용 (W21~W26)
                w = 21 + (c_idx - 19) // 2
                
            # 주간 인당검색건 수치(c_idx == 19, 21, 23, 25, 27, 29)에 Supabase 계산값 주입
            # 오프셋 없이 실제 iso_week 번호(w)로 직접 조회
            if w != -1 and (c_idx - 19) % 2 == 0:
                center_name = trend_df.iloc[r_idx, 3] # col 3 is 담당/센터
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    if c_name in weekly_center_metrics and w in weekly_center_metrics[c_name]:
                        val = f"{weekly_center_metrics[c_name][w]:.1f}"
                    else:
                        # 데이터가 없는 주차는 '-'(하이픈) 표시 (흰색)
                        val = "-"

            # 주간 참여율 수치(c_idx == 20, 22, 24, 26, 28, 30)에 Supabase 계산값 주입
            if w != -1 and (c_idx - 19) % 2 == 1:
                center_name = trend_df.iloc[r_idx, 3]
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    if 'weekly_participation_rate' in locals() and c_name in weekly_participation_rate and w in weekly_participation_rate[c_name]:
                        rate_val = weekly_participation_rate[c_name][w]
                        if rate_val >= 0:
                            val = f"{rate_val:.1f}%"
                        else:
                            val = "-"
                                
            class_attr = ""
            if m != -1:
                class_attr = f" class='month-col month-{m}'"
            elif w != -1:
                class_attr = f" class='week-col week-{w}'"

            # W21(c_idx==19) 데이터 출력 직전에 W1~W20 데이터 추가
            # → W18, W19처럼 실제 ISO 주차가 1~20인 데이터는 여기서 표시됨
            if c_idx == 19:
                for w_ex in range(1, 21):
                    w_val1 = ""
                    p_val1 = ""
                    center_name = trend_df.iloc[r_idx, 3]
                    if pd.notna(center_name):
                        c_name = str(center_name).strip()
                        # 오프셋 없이 실제 iso_week 번호로 직접 조회 (W18→18, W19→19)
                        if c_name in weekly_center_metrics and w_ex in weekly_center_metrics[c_name]:
                            w_val1 = f"{weekly_center_metrics[c_name][w_ex]:.1f}"
                        if 'weekly_participation_rate' in locals() and c_name in weekly_participation_rate and w_ex in weekly_participation_rate[c_name]:
                            r_val = weekly_participation_rate[c_name][w_ex]
                            if r_val >= 0:
                                p_val1 = f"{r_val:.1f}%"
                            else:
                                p_val1 = "-"
                    trend_html += f"      <td class='week-col week-{w_ex}'>{w_val1}</td>\n"
                    trend_html += f"      <td class='week-col week-{w_ex}'>{p_val1}</td>\n"
            
            trend_html += f"      <td{class_attr}>{val}</td>\n"
            
            # 6월 데이터 끝난 직후(c_idx==17) 7~12월 데이터 추가
            # → 7월 이후 데이터도 Supabase에 올리면 자동 표시
            if c_idx == 17:
                center_name_17 = trend_df.iloc[r_idx, 3]
                for m_ex in range(7, 13):
                    m_val1 = ""
                    p_val1 = ""
                    if pd.notna(center_name_17):
                        c_name_17 = str(center_name_17).strip()
                        if c_name_17 in monthly_center_metrics and m_ex in monthly_center_metrics[c_name_17]:
                            m_val1 = f"{monthly_center_metrics[c_name_17][m_ex]:.1f}"
                        if 'monthly_participation_rate' in locals() and c_name_17 in monthly_participation_rate and m_ex in monthly_participation_rate[c_name_17]:
                            r_val = monthly_participation_rate[c_name_17][m_ex]
                            if r_val > 0:
                                p_val1 = f"{r_val:.1f}%"
                            else:
                                p_val1 = "-"
                    trend_html += f"      <td class='month-col month-{m_ex}'>{m_val1}</td>\n"
                    trend_html += f"      <td class='month-col month-{m_ex}'>{p_val1}</td>\n"
                    
            # W26 데이터 끝난 직후(c_idx==30) W27~W52 데이터 추가
            # 오프셋 없이 실제 iso_week 번호로 직접 조회
            if c_idx == 30:
                for w_ex in range(27, 53):
                    w_val1 = ""
                    p_val1 = ""
                    center_name = trend_df.iloc[r_idx, 3]
                    if pd.notna(center_name):
                        c_name = str(center_name).strip()
                        if c_name in weekly_center_metrics and w_ex in weekly_center_metrics[c_name]:
                            w_val1 = f"{weekly_center_metrics[c_name][w_ex]:.1f}"
                        if 'weekly_participation_rate' in locals() and c_name in weekly_participation_rate and w_ex in weekly_participation_rate[c_name]:
                            r_val = weekly_participation_rate[c_name][w_ex]
                            if r_val >= 0:
                                p_val1 = f"{r_val:.1f}%"
                            else:
                                p_val1 = "-"
                                    
                    trend_html += f"      <td class='week-col week-{w_ex}'>{w_val1}</td>\n"
                    trend_html += f"      <td class='week-col week-{w_ex}'>{p_val1}</td>\n"
        trend_html += "    </tr>\n"
    trend_html += "  </tbody>\n"
    trend_html += "</table>\n"
    
    # 좌우 슬라이드 기능 JS 주입
    trend_html += """
    <script>
    let currentStartMonth = 1;
    const visibleCount = 6; // 한 번에 보여줄 개월 수
    
    function updateMonthDisplay() {
        let visibleCols = 0;
        for(let m=1; m<=12; m++) {
            let isVisible = (m >= currentStartMonth && m < currentStartMonth + visibleCount);
            let displayVal = isVisible ? '' : 'none';
            
            let cols = document.querySelectorAll('.month-' + m);
            cols.forEach(el => {
                el.style.display = displayVal;
            });
            if(isVisible) visibleCols += 2;
        }
        let monthHeader = document.getElementById('monthly-master-header');
        if(monthHeader) {
            monthHeader.colSpan = visibleCols;
        }
    }
    
    function slideMonth(dir) {
        currentStartMonth += dir;
        if (currentStartMonth < 1) currentStartMonth = 1;
        if (currentStartMonth > 12 - visibleCount + 1) currentStartMonth = 12 - visibleCount + 1;
        updateMonthDisplay();
    }
    
    let currentStartWeek = 1;
    const visibleWeekCount = 6; // 한 번에 보여줄 주차 수
    
    function updateWeekDisplay() {
        let visibleCols = 0;
        for(let w=1; w<=52; w++) {
            let isVisible = (w >= currentStartWeek && w < currentStartWeek + visibleWeekCount);
            let displayVal = isVisible ? '' : 'none';
            
            let cols = document.querySelectorAll('.week-' + w);
            cols.forEach(el => {
                el.style.display = displayVal;
            });
            if(isVisible) visibleCols += 2;
        }
        let weekHeader = document.getElementById('weekly-master-header');
        if(weekHeader) {
            weekHeader.colSpan = visibleCols;
        }
    }
    
    function slideWeek(dir) {
        currentStartWeek += dir;
        if (currentStartWeek < 1) currentStartWeek = 1;
        if (currentStartWeek > 52 - visibleWeekCount + 1) currentStartWeek = 52 - visibleWeekCount + 1;
        updateWeekDisplay();
    }
    
    // 초기 실행
    updateMonthDisplay();
    updateWeekDisplay();
    </script>
    """
except Exception as e:
    import traceback
    err_trace = traceback.format_exc()
    print(f"Error generating trend table:\n{err_trace}")
    trend_html = f"<div style='padding: 20px; text-align: center; color: #ff6b6b;'>데이터를 불러오는 데 실패했습니다: <br><pre>{err_trace}</pre></div>"

# index.html 내의 플레이스홀더 치환
html = re.sub(
    r'(<!-- TREND_TABLE_START -->)[\s\S]*?(<!-- TREND_TABLE_END -->)',
    f'\\g<1>\n{trend_html}\n\\g<2>',
    html
)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated index.html")
import json; print(list(weekly_participation_rate.keys())[:5])
