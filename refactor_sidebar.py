import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add CSS
css_to_add = """
        /* ─── 사이드바 구조 ─── */
        body {
            display: flex;
            height: 100vh;
            overflow: hidden;
            margin: 0;
            padding: 0;
            background: #0b0f19;
        }

        .sidebar {
            width: 260px;
            background: #11151e;
            border-right: 1px solid #252d3f;
            display: flex;
            flex-direction: column;
            padding: 24px 0;
            flex-shrink: 0;
            z-index: 100;
        }

        .sidebar-brand {
            padding: 0 24px;
            margin-bottom: 32px;
        }

        .sidebar-brand .brand-name {
            font-size: 18px;
            font-weight: 800;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .sidebar-brand .brand-sub {
            font-size: 11px;
            color: #64748b;
            margin-top: 8px;
            line-height: 1.4;
        }

        .sidebar-menu {
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 0 16px;
        }

        .sidebar-menu .tab {
            background: transparent;
            border: none;
            color: #a0aec0;
            font-size: 14px;
            font-weight: 600;
            padding: 14px 16px;
            border-radius: 8px;
            text-align: left;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .sidebar-menu .tab:hover {
            background: #1e2433;
            color: #fff;
        }

        .sidebar-menu .tab.active {
            background: #4f46e5;
            color: #fff;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        }

        .main-content {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .main-scroll {
            flex-grow: 1;
            overflow-y: auto;
            padding: 0 32px 32px 32px;
        }
        
        /* 헤더 스타일 덮어쓰기 */
        .hdr {
            position: sticky;
            top: 0;
            z-index: 50;
            background: rgba(11,15,25,0.9);
            backdrop-filter: blur(8px);
            justify-content: flex-end;
        }
        .hdr .hdr-brand, .hdr .tabs {
            display: none !important;
        }
"""
# Insert CSS before </style>
html = html.replace('</style>', css_to_add + '\n    </style>')

# 2. Modify Body Structure
# Find <body> tag
body_start = html.find('<body>')
if body_start != -1:
    # Sidebar HTML
    sidebar_html = """
    <aside class="sidebar">
        <div class="sidebar-brand">
            <div class="brand-name">🤖 챗봇 인텔리전스</div>
            <div class="brand-sub">LG전자 서비스센터 AI 챗봇<br>관리자 대시보드</div>
        </div>
        <nav class="sidebar-menu">
            <button class="tab active" onclick="switchTab('u',this)">👥 종합 현황</button>
            <button class="tab" onclick="switchTab('t',this)">📋 담당/센터별 현황판</button>
            <button class="tab" onclick="switchTab('p',this)">📦 제품별 현황</button>
            <button class="tab" onclick="switchTab('q',this)">📊 데이터 품질</button>
        </nav>
    </aside>
    <div class="main-content">
        <!-- 기존 Header는 main-content 안에 둠 (통계 표시용) -->
"""
    # Replace <body> with <body> + sidebar_html
    html = html.replace('<body>', '<body>\n' + sidebar_html)

# 3. Wrap Pages in main-scroll
# Find the start of page-u
page_u_start = html.find('<!-- ══════════════════════════════ 사용자 현황 ══════════════════════════════ -->')
if page_u_start != -1:
    html = html[:page_u_start] + '        <div class="main-scroll">\n' + html[page_u_start:]

# Find the closing tag of the body
body_end = html.find('<script>')
if body_end != -1:
    # Close main-scroll and main-content before script
    html = html[:body_end] + '        </div>\n    </div>\n\n    ' + html[body_end:]

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("done")
