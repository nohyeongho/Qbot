import pandas as pd
import math

df = pd.read_excel('01_Qbot trend.xlsx', header=None)

# Headers start at row 2, 3, 4 (index 1, 2, 3)
html = "<table class='trend-table'>\n"
html += "  <thead>\n"

# Row 1 (index 1 in excel but we exported as csv which has row 1 empty, row 2 '소속,소속,소속,년간,,월간...')
# Let's inspect df.iloc[1:4]
for r_idx in range(1, 4):
    html += "    <tr>\n"
    for c_idx in range(len(df.columns)):
        val = df.iloc[r_idx, c_idx]
        if pd.isna(val):
            val = ""
        else:
            val = str(val).replace('\n', '<br>')
        html += f"      <th>{val}</th>\n"
    html += "    </tr>\n"
html += "  </thead>\n"
html += "  <tbody>\n"

for r_idx in range(4, len(df)):
    html += "    <tr>\n"
    # check if row is empty
    if pd.isna(df.iloc[r_idx, 0]) and pd.isna(df.iloc[r_idx, 1]) and pd.isna(df.iloc[r_idx, 2]):
        continue
        
    for c_idx in range(len(df.columns)):
        val = df.iloc[r_idx, c_idx]
        if pd.isna(val):
            val = ""
        elif isinstance(val, (int, float)):
            if math.isnan(val):
                val = ""
            else:
                val = f"{val:.1f}" if val < 10 else str(int(val)) # format numbers roughly
        else:
            val = str(val)
        html += f"      <td>{val}</td>\n"
    html += "    </tr>\n"

html += "  </tbody>\n"
html += "</table>\n"

with open('test_table.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("done")
