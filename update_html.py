import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add IDs to KPI values if they don't exist
# We will just replace specific known blocks or add a script to dynamically fetch them.
# It's easier to find the exact KPI blocks. 
# "전체 사용자", "총 문의건수", "응답 완결률"
html = re.sub(r'(<div class="kpi-label">전체 사용자</div>\s*)<div class="kpi-val">(.*?)</div>', r'\1<div class="kpi-val" id="kpi-users">\2</div>', html)
html = re.sub(r'(<div class="kpi-label">총 문의건수</div>\s*)<div class="kpi-val">(.*?)</div>', r'\1<div class="kpi-val" id="kpi-inquiries">\2</div>', html)
html = re.sub(r'(<div class="kpi-label">응답 완결률</div>\s*)<div class="kpi-val">(.*?)</div>', r'\1<div class="kpi-val" id="kpi-resolve-rate">\2</div>', html)

# 2. Replace Chart data with fetch logic
# Instead of replacing everything, we will inject a fetch function at the top of the JS block.
fetch_script = """
        // 백엔드 API 연동 함수
        async function fetchDashboardData() {
            try {
                // KPI 데이터 가져오기
                const kpiRes = await fetch('http://localhost:8000/api/kpis');
                if (kpiRes.ok) {
                    const kpiData = await kpiRes.json();
                    document.getElementById('kpi-users').innerText = kpiData.total_users;
                    document.getElementById('kpi-inquiries').innerText = kpiData.total_inquiries;
                    document.getElementById('kpi-resolve-rate').innerText = kpiData.resolve_rate + '%';
                }

                // 시간대별 차트 데이터 가져오기
                const hourlyRes = await fetch('http://localhost:8000/api/charts/hourly');
                if (hourlyRes.ok) {
                    const hourlyData = await hourlyRes.json();
                    const cHourChart = Chart.getChart('cHour');
                    if (cHourChart) {
                        cHourChart.data.labels = hourlyData.labels;
                        cHourChart.data.datasets[0].data = hourlyData.data;
                        cHourChart.update();
                    }
                }

                // 유형별 차트 데이터 가져오기
                const typesRes = await fetch('http://localhost:8000/api/charts/types');
                if (typesRes.ok) {
                    const typesData = await typesRes.json();
                    const cTypeChart = Chart.getChart('cType');
                    if (cTypeChart) {
                        cTypeChart.data.labels = typesData.labels;
                        cTypeChart.data.datasets[0].data = typesData.data;
                        cTypeChart.update();
                    }
                }
                
                // 순위 차트 데이터 가져오기
                const rankRes = await fetch('http://localhost:8000/api/rankings');
                if (rankRes.ok) {
                    const rankData = await rankRes.json();
                    
                    const cUserChart = Chart.getChart('cUserBar');
                    if (cUserChart) {
                        cUserChart.data.labels = rankData.top_users.labels;
                        cUserChart.data.datasets[0].data = rankData.top_users.data;
                        cUserChart.update();
                    }
                    
                    const cCenterChart = Chart.getChart('cCenterBubble');
                    if (cCenterChart) {
                        // 버블 차트는 형태가 다름: x, y, r
                        const newData = rankData.top_centers.data.map((v, i) => ({ x: i + 1, y: v, r: v > 1000 ? v/500 : (v > 100 ? v/50 : v/5) + 3 }));
                        cCenterChart.data.datasets[0].data = newData;
                        // x축 라벨 콜백을 위해 labels도 업데이트
                        cCenterChart.options.scales.x.ticks.callback = function(value) {
                            return rankData.top_centers.labels[value - 1] || '';
                        };
                        cCenterChart.options.plugins.tooltip.callbacks.label = ctx => `${rankData.top_centers.labels[ctx.dataIndex]}: ${ctx.raw.y}건`;
                        cCenterChart.update();
                    }
                }
            } catch (err) {
                console.error("API 연동 오류:", err);
            }
        }
        
        // 페이지 로딩 완료 후 API 호출
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(fetchDashboardData, 500); // 차트 초기화 후 호출
        });
"""

# We can append this fetch script right before the closing </script>
html = html.replace('</script>\n</body>', fetch_script + '\n</script>\n</body>')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("index.html updated successfully!")
