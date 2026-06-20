import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. 탭 버튼 추가
html = html.replace(
    '<button class="tab" onclick="switchTab(\'p\',this)">📦 제품별 현황</button>',
    '<button class="tab" onclick="switchTab(\'t\',this)">📈 담당/센터 현황</button>\n            <button class="tab" onclick="switchTab(\'p\',this)">📦 제품별 현황</button>'
)

# 2. page-u 시작 부분에서 trend-board-wrapper 추출
# trend-board-wrapper 시작부터 그 닫는 div </div> 까지 찾아야 하는데, 
# 정규식으로 안전하게 잡기 위해 kpi-row 시작 전까지를 자름.

match = re.search(r'(<!-- 담당/센터별 현황판 -->[\s\S]*?)(?=\s*<div class="kpi-row">)', html)
if match:
    trend_html = match.group(1)
    
    # page-u에서 삭제
    html = html.replace(trend_html, '')
    
    # page-t 탭 컨테이너 생성 후 page-p 위에 삽입
    page_t = f'''
    <!-- ══════════════════════════════ 담당/센터별 현황 ══════════════════════════════ -->
    <div id="page-t" class="page">
{trend_html}
    </div>
'''
    html = html.replace(
        '<!-- ══════════════════════════════ 제품별 현황 ══════════════════════════════ -->',
        page_t + '\n    <!-- ══════════════════════════════ 제품별 현황 ══════════════════════════════ -->'
    )

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("done")
