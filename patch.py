import re

with open('update_index.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Change w calculation for headers
content = re.sub(
    r'elif r_idx == 2 and c_idx in \[19, 21, 23, 25, 27, 29\]:\s+w = 21 \+ \(c_idx - 19\) // 2\s+class_attr = f\" class=\'week-col week-\{w\}\'\"',
    r'''elif r_idx == 2 and c_idx in [19, 21, 23, 25, 27, 29]:
                    w = 1 + (c_idx - 19) // 2
                    class_attr = f" class='week-col week-{w}'"
                    val = f"W{w}"''',
    content
)

# 2. Remove W1~W20 dummy loops
content = re.sub(
    r'# W21\(c_idx==19\) 출력 직전??W1~W20 추?\s+if r_idx == 2 and c_idx == 19:\s+for w_ex in range\(1, 21\):\s+trend_html \+= f"      <th colspan=\'2\' class=\'week-col week-\{w_ex\}\'>W\{w_ex\}</th>\\n"',
    r'# W21(c_idx==19) 출력 직전??W1~W20 추? (제거됨)',
    content
)

# 3. Change w calculation for sub-headers and data
content = re.sub(
    r'w = -1\s+if 19 <= c_idx <= 30:\s+w = 21 \+ \(c_idx - 19\) // 2',
    r'''w = -1
                if 19 <= c_idx <= 30:
                    w = 1 + (c_idx - 19) // 2''',
    content
)

# 4. Remove W1~W20 dummy sub-headers
content = re.sub(
    r'# W21\(c_idx==19\) ?위 ?더 직전??W1~W20 ?위 ?더 추?\s+if c_idx == 19:\s+for w_ex in range\(1, 21\):\s+trend_html \+= f"      <th class=\'week-col week-\{w_ex\}\'>\?당<br>검\?건</th>\\n"\s+trend_html \+= f"      <th class=\'week-col week-\{w_ex\}\'>참여\?\?th>\\n"',
    r'# W21(c_idx==19) ?위 ?더 직전??W1~W20 ?위 ?더 추? (제거됨)',
    content
)

# 5. Fix Supabase lookup for w
content = re.sub(
    r'if c_name in weekly_center_metrics and w in weekly_center_metrics\[c_name\]:\s+val = f"\{weekly_center_metrics\[c_name\]\[w\]:\.1f\}"',
    r'''if c_name in weekly_center_metrics and (w + 20) in weekly_center_metrics[c_name]:
                        val = f"{weekly_center_metrics[c_name][w + 20]:.1f}"''',
    content
)

# 6. Remove W1~W20 dummy data
content = re.sub(
    r'# W21\(c_idx==19\) ?이\?\?출력 직전??W1~W20 ?이\?\?빈칸 추?\s+if c_idx == 19:\s+for w_ex in range\(1, 21\):\s+w_val1 = ""\s+center_name = trend_df\.iloc\[r_idx, 3\]\s+if pd\.notna\(center_name\):\s+c_name = str\(center_name\)\.strip\(\)\s+if c_name in weekly_center_metrics and w_ex in weekly_center_metrics\[c_name\]:\s+w_val1 = f"\{weekly_center_metrics\[c_name\]\[w_ex\]:\.1f\}"\s+else:\s+w_val1 = "0\.0"\s+trend_html \+= f"      <td class=\'week-col week-\{w_ex\}\'>\{w_val1\}</td>\\n"\s+trend_html \+= f"      <td class=\'week-col week-\{w_ex\}\'></td>\\n"',
    r'# W21(c_idx==19) ?이\?\?출력 직전??W1~W20 ?이\?\?빈칸 추? (제거됨)',
    content
)

# 7. Shift W27~W52 dummy data
content = re.sub(
    r'# W26 ?이\?\??난 직후\(c_idx==30\) W27~W52 ?이\?\?빈칸 추?\s+if c_idx == 30:\s+for w_ex in range\(27, 53\):\s+w_val1 = ""\s+center_name = trend_df\.iloc\[r_idx, 3\]\s+if pd\.notna\(center_name\):\s+c_name = str\(center_name\)\.strip\(\)\s+if c_name in weekly_center_metrics and w_ex in weekly_center_metrics\[c_name\]:\s+w_val1 = f"\{weekly_center_metrics\[c_name\]\[w_ex\]:\.1f\}"\s+else:\s+w_val1 = "0\.0"\s+trend_html \+= f"      <td class=\'week-col week-\{w_ex\}\'>\{w_val1\}</td>\\n"\s+trend_html \+= f"      <td class=\'week-col week-\{w_ex\}\'></td>\\n"',
    r'''# W26 데이터 지난 직후(c_idx==30) W7~W52 데이터 빈칸 추가 (shifted by 20)
            if c_idx == 30:
                for w_ex in range(7, 53):
                    w_val1 = ""
                    center_name = trend_df.iloc[r_idx, 3]
                    if pd.notna(center_name):
                        c_name = str(center_name).strip()
                        if c_name in weekly_center_metrics and (w_ex + 20) in weekly_center_metrics[c_name]:
                            w_val1 = f"{weekly_center_metrics[c_name][w_ex + 20]:.1f}"
                        else:
                            w_val1 = "0.0"
                                    
                    trend_html += f"      <td class='week-col week-{w_ex}'>{w_val1}</td>\n"
                    trend_html += f"      <td class='week-col week-{w_ex}'></td>\n"''',
    content
)

with open('update_index_patched.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch script complete.")
