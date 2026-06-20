import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the previous fetchDashboardData with the Supabase version
supabase_script = """
        // Supabase 연동 변수
        const SUPA_URL = 'https://seanzwnadqaneusqeami.supabase.co/rest/v1';
        const SUPA_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI';
        const headers = {
            'apikey': SUPA_KEY,
            'Authorization': 'Bearer ' + SUPA_KEY
        };

        // 백엔드 API 연동 함수 (Supabase)
        async function fetchDashboardData() {
            try {
                // KPI 데이터 가져오기
                const kpiRes = await fetch(`${SUPA_URL}/v_kpis?select=*`, { headers });
                if (kpiRes.ok) {
                    const kpiData = await kpiRes.json();
                    if (kpiData.length > 0) {
                        document.getElementById('kpi-users').innerText = kpiData[0].total_users || 0;
                        document.getElementById('kpi-inquiries').innerText = kpiData[0].total_inquiries || 0;
                        
                        let resolve_rate = 0;
                        if (kpiData[0].total_inquiries > 0) {
                            resolve_rate = ((kpiData[0].resolved_count / kpiData[0].total_inquiries) * 100).toFixed(1);
                        }
                        document.getElementById('kpi-resolve-rate').innerText = resolve_rate + '%';
                        
                        // 의도: Supabase 모드에서도 상단 헤더 영역의 전체 사용자 수와 총 검색건수를 동적 바인딩합니다.
                        const hdrUsers = document.getElementById('hdr-users');
                        if (hdrUsers) hdrUsers.innerText = Number(kpiData[0].total_users || 0).toLocaleString();
                        const hdrInq = document.getElementById('hdr-inquiries');
                        if (hdrInq) hdrInq.innerText = Number(kpiData[0].total_inquiries || 0).toLocaleString();
                        
                        // 의도: Supabase 모드에서 가져온 실제 활성 일수(active_days)로 일평균 검색 건수를 동적 계산합니다.
                        const active_days = kpiData[0].active_days || 31;
                        const avgVal = ((kpiData[0].total_inquiries || 0) / active_days).toFixed(1);
                        
                        // 평일(Working Day) 기준 데이터
                        const active_days_wd = kpiData[0].active_days_wd || 21;
                        const avgValWd = ((kpiData[0].total_inquiries_wd || 0) / active_days_wd).toFixed(1);
                        const sum_daily_users_wd = kpiData[0].sum_daily_users_wd || 0;
                        const avgUsersWd = Math.round(sum_daily_users_wd / active_days_wd);
                        
                        const usersWdElem = document.getElementById('kpi-users-wd');
                        if (usersWdElem) {
                            usersWdElem.innerText = `Working Day 일평균: ${avgUsersWd.toLocaleString()}명`;
                        }
                        
                        const inquiriesAvgElem = document.getElementById('kpi-inquiries-avg');
                        if (inquiriesAvgElem) {
                            inquiriesAvgElem.innerHTML = `<span style="color:#38b67a;">Working Day 일평균 ${Number(avgValWd).toLocaleString()}건</span>`;
                        }
                    }
                }

                // 시간대별 차트 데이터 가져오기
                const hourlyRes = await fetch(`${SUPA_URL}/v_hourly?select=*`, { headers });
                if (hourlyRes.ok) {
                    const hourlyData = await hourlyRes.json();
                    const labels = [];
                    const data = [];
                    for (let i = 0; i < 24; i++) {
                        labels.push(i.toString().padStart(2, '0'));
                        const hourRow = hourlyData.find(r => r.chat_hour === i);
                        data.push(hourRow ? hourRow.inquiry_count : 0);
                    }
                    
                    const cHourChart = Chart.getChart('cHour');
                    if (cHourChart) {
                        cHourChart.data.labels = labels;
                        cHourChart.data.datasets[0].data = data;
                        cHourChart.update();
                    }
                }

                // 유형별 차트 데이터 가져오기
                const typesRes = await fetch(`${SUPA_URL}/v_types?select=*`, { headers });
                if (typesRes.ok) {
                    const typesData = await typesRes.json();
                    
                    let tech = 0, symp = 0, spec = 0, other = 0;
                    typesData.forEach(r => {
                        if (r.question_type === 'UNIFIED_TECH') tech += r.type_count;
                        else if (r.question_type === 'MODEL_SYMPTOM') symp += r.type_count;
                        else if (r.question_type === 'SPEC_INFO') spec += r.type_count;
                        else other += r.type_count;
                    });
                    
                    const cTypeChart = Chart.getChart('cType');
                    if (cTypeChart) {
                        cTypeChart.data.labels = ['통합기술', '모델증상', '스펙조회', '기타'];
                        cTypeChart.data.datasets[0].data = [tech, symp, spec, other];
                        cTypeChart.update();
                    }
                }
                
                // 순위 차트 데이터 가져오기 (사용자 10명)
                const userRes = await fetch(`${SUPA_URL}/v_top_users?select=*`, { headers });
                if (userRes.ok) {
                    const userData = await userRes.json();
                    const cUserChart = Chart.getChart('cUserBar');
                    if (cUserChart) {
                        cUserChart.data.labels = userData.map(r => r.user_name);
                        cUserChart.data.datasets[0].data = userData.map(r => r.inquiry_count);
                        cUserChart.update();
                    }
                }
                
                // 순위 차트 데이터 가져오기 (센터 10곳)
                const centerRes = await fetch(`${SUPA_URL}/v_top_centers?select=*`, { headers });
                if (centerRes.ok) {
                    const centerData = await centerRes.json();
                    const cCenterChart = Chart.getChart('cCenterBubble');
                    if (cCenterChart) {
                        const labels = centerData.map(r => r.user_dept_name);
                        const newData = centerData.map((r, i) => {
                            const v = r.inquiry_count;
                            return { x: i + 1, y: v, r: v > 1000 ? v/500 : (v > 100 ? v/50 : v/5) + 3 };
                        });
                        cCenterChart.data.datasets[0].data = newData;
                        cCenterChart.options.scales.x.ticks.callback = function(value) {
                            return labels[value - 1] || '';
                        };
                        cCenterChart.options.plugins.tooltip.callbacks.label = ctx => `${labels[ctx.dataIndex]}: ${ctx.raw.y}건`;
                        cCenterChart.update();
                    }
                }
            } catch (err) {
                console.error("Supabase API 연동 오류:", err);
            }
        }
        
        // 페이지 로딩 완료 후 API 호출
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(fetchDashboardData, 500); // 차트 초기화 후 호출
        });
"""

# Extract the old fetch function using regex and replace it
# We know it starts with "// 백엔드 API 연동 함수" and ends with "});" at the end of the script block
old_pattern = re.compile(r'// 백엔드 API 연동 함수.*?document\.addEventListener\(\'DOMContentLoaded\', \(\) => \{\s*setTimeout\(fetchDashboardData, 500\);.*?\}\);', re.DOTALL)
html = old_pattern.sub(supabase_script.strip(), html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Supabase config injected into index.html!")
