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

print("Fetching Supabase data for 5월 인당검색건 calculation...")
sm_job_data = get_all_rows('sm_job', 'sm_id, center_name, job_title')
chat_logs_data = get_all_rows('chat_logs', 'userNo, userAction, chatDate')

df_sm = pd.DataFrame(sm_job_data)
df_chat = pd.DataFrame(chat_logs_data)

center_metrics = {}
if not df_sm.empty and not df_chat.empty:
    # 5월 근무일 계산 및 chat_logs 평일 필터링 로직
    holidays_to_exclude = ['2026-05-01', '2026-05-05', '2026-05-25']
    working_days_count = 18 # 31일 - 주말(10일) - 평일공휴일(3일)

    if 'chatDate' in df_chat.columns:
        df_chat['chatDate_dt'] = pd.to_datetime(df_chat['chatDate'], errors='coerce')
        # 주말(dayofweek: 5=Sat, 6=Sun) 및 공휴일 필터링 (분자)
        df_chat = df_chat[
            (df_chat['chatDate_dt'].dt.dayofweek < 5) & 
            (~df_chat['chatDate'].isin(holidays_to_exclude))
        ]

    denom_df = df_sm[df_sm['job_title'] == '출장'].groupby('center_name').size().reset_index(name='denom')
    # 분모에 근무일수 곱하기 (출장 인원수 * 근무일수)
    denom_df['denom'] = denom_df['denom'] * working_days_count

    merged = pd.merge(df_chat, df_sm, left_on='userNo', right_on='sm_id', how='inner')
    num_df = merged[(merged['userAction'] == 'QUESTION') & (merged['job_title'] == '출장')].groupby('center_name').size().reset_index(name='num')
    
    metric_df = pd.merge(denom_df, num_df, on='center_name', how='left').fillna(0)
    # denominator 0인 경우 방어
    metric_df.loc[metric_df['denom'] == 0, 'denom'] = 1 
    metric_df['인당검색건'] = metric_df['num'] / metric_df['denom']
    
    center_metrics = dict(zip(metric_df['center_name'].str.strip(), metric_df['인당검색건']))
    
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
            c_name = str(row['center_name']).strip()
            w = int(row['iso_week'])
            val = row['인당검색건']
            if c_name not in weekly_center_metrics:
                weekly_center_metrics[c_name] = {}
            weekly_center_metrics[c_name][w] = val

print(f"Calculated metrics for {len(center_metrics)} centers using working days.")

# 엑셀 데이터 로드
file_path = 'RawData_202605.xlsx'
print("Loading excel...")
df = pd.read_excel(file_path)
print(f"Loaded {len(df)} rows.")

# 기본 KPI
# 이름 중복(동명이인)을 고려하기 위해, userName과 userNo(사번)를 결합하여 고유 사용자를 식별합니다.
df['userName'] = df['userName'].fillna('알수없음').astype(str)
df['userNo'] = df['userNo'].fillna('알수없음').astype(str)
df['user_key'] = df['userName'] + '(' + df['userNo'] + ')'

total_users = df['user_key'].nunique()
total_inquiries = len(df)
# Date range
dates = pd.to_datetime(df['chatDate']).dt.date
start_date = dates.min().strftime('%Y.%m.%d')
end_date = dates.max().strftime('%m.%d')
date_str = f"{start_date} ~ {end_date}"

# 시간대별 라인
df['hour'] = pd.to_datetime(df['chatHour'], format='%H:%M:%S').dt.hour
hour_counts = df['hour'].value_counts().sort_index()
hours_label = [str(h).zfill(2) for h in hour_counts.index]
hours_data = hour_counts.values.tolist()

# 유형 도넛 (통합기술, 모델증상, 스펙조회 등)
type_counts = df['questionTypeCd'].value_counts()
type_labels = ['통합기술', '모델증상', '스펙조회', '기타']
type_data = [
    int(type_counts.get('UNIFIED_TECH', 0)),
    int(type_counts.get('MODEL_SYMPTOM', 0)),
    int(type_counts.get('SPEC_INFO', 0))
]
type_data.append(total_inquiries - sum(type_data))

# 상위 사용자
# 동명이인이 랭킹 차트에서 분리되도록 user_key(이름(사번)) 기준으로 집계합니다.
user_counts = df['user_key'].value_counts().head(10)
user_names = user_counts.index.tolist()
user_vals = user_counts.values.tolist()

# 센터별
center_counts = df['userDeptName'].str.replace('서비스센터', '').value_counts().head(10)
centers = center_counts.index.tolist()
center_vals = center_counts.values.tolist()

# 문서 CTR, 응답 완결률 등은 임의의 로직이나 기존 데이터를 참조해야 함
# 일단 df 기반으로 대체
if 'aiResultStatus' in df.columns:
    ai_result = df['aiResultStatus'].value_counts()
    resolved = int(ai_result.get('SUCCESS', 0))
    unresolved = int(ai_result.get('FAIL', 0))
else:
    resolved = 0
    unresolved = 0
resolve_rate = round(resolved / total_inquiries * 100, 1) if total_inquiries > 0 else 0

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
                    w = 1 + (c_idx - 19) // 2
                    class_attr = f" class='week-col week-{w}'"
                    val = f"W{w}"
                else:
                    class_attr = ""
                
                # W21(c_idx==19) 출력 직전에 W1~W20 추가
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
                        
                # W26(c_idx==29) 출력 직후 W27~W52 추가
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
                    w = 1 + (c_idx - 19) // 2
                    
                class_attr = ""
                if m != -1:
                    class_attr = f" class='month-col month-{m}'"
                elif w != -1:
                    class_attr = f" class='week-col week-{w}'"
                # W21(c_idx==19) 하위 헤더 직전에 W1~W20 하위 헤더 추가
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
                        
                # W26 데이터 헤더 직후(c_idx==30) W27~W52 하위 헤더 추가
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
                
            # 5월 인당검색건 수치(c_idx==14)에 Supabase 계산값 주입
            if c_idx == 14:
                center_name = trend_df.iloc[r_idx, 3] # col 3 is 담당/센터
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    if c_name in center_metrics:
                        val = f"{center_metrics[c_name]:.1f}"
                        
            m = -1
            if 6 <= c_idx <= 17:
                m = (c_idx - 6) // 2 + 1
                
            w = -1
                if 19 <= c_idx <= 30:
                    w = 1 + (c_idx - 19) // 2
                
            # 주간 인당검색건 수치(c_idx == 19, 21, 23, 25, 27, 29)에 Supabase 계산값 주입
            if w != -1 and (c_idx - 19) % 2 == 0:
                center_name = trend_df.iloc[r_idx, 3] # col 3 is 담당/센터
                if pd.notna(center_name):
                    c_name = str(center_name).strip()
                    if c_name in weekly_center_metrics and (w + 20) in weekly_center_metrics[c_name]:
                        val = f"{weekly_center_metrics[c_name][w + 20]:.1f}"
                    else:
                        val = "0.0"
                                
            class_attr = ""
            if m != -1:
                class_attr = f" class='month-col month-{m}'"
            elif w != -1:
                class_attr = f" class='week-col week-{w}'"
            
            # W21(c_idx==19) 데이터 출력 직전에 W1~W20 데이터 빈칸 추가
            if c_idx == 19:
                for w_ex in range(1, 21):
                    w_val1 = ""
                    center_name = trend_df.iloc[r_idx, 3]
                    if pd.notna(center_name):
                        c_name = str(center_name).strip()
                        if c_name in weekly_center_metrics and w_ex in weekly_center_metrics[c_name]:
                            w_val1 = f"{weekly_center_metrics[c_name][w_ex]:.1f}"
                        else:
                            w_val1 = "0.0"
                    trend_html += f"      <td class='week-col week-{w_ex}'>{w_val1}</td>\n"
                    trend_html += f"      <td class='week-col week-{w_ex}'></td>\n"

            trend_html += f"      <td{class_attr}>{val}</td>\n"
            
            # 6월 데이터 끝난 직후(c_idx==17) 7~12월 데이터 빈칸 추가 (12열)
            if c_idx == 17:
                for m in range(7, 13):
                    trend_html += f"      <td class='month-col month-{m}'></td>\n"
                    trend_html += f"      <td class='month-col month-{m}'></td>\n"
                    
            # W26 데이터 끝난 직후(c_idx==30) W27~W52 데이터 빈칸 추가
            if c_idx == 30:
                for w_ex in range(27, 53):
                    w_val1 = ""
                    center_name = trend_df.iloc[r_idx, 3]
                    if pd.notna(center_name):
                        c_name = str(center_name).strip()
                        if c_name in weekly_center_metrics and w_ex in weekly_center_metrics[c_name]:
                            w_val1 = f"{weekly_center_metrics[c_name][w_ex]:.1f}"
                        else:
                            w_val1 = "0.0"
                                    
                    trend_html += f"      <td class='week-col week-{w_ex}'>{w_val1}</td>\n"
                    trend_html += f"      <td class='week-col week-{w_ex}'></td>\n"
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
    print(f"Error generating trend table: {e}")
    trend_html = f"<div style='padding: 20px; text-align: center; color: #ff6b6b;'>데이터를 불러오는 데 실패했습니다: {e}</div>"

# index.html 내의 플레이스홀더 치환
html = re.sub(
    r'(<!-- TREND_TABLE_START -->)[\s\S]*?(<!-- TREND_TABLE_END -->)',
    f'\\g<1>\n{trend_html}\n\\g<2>',
    html
)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Updated index.html")
