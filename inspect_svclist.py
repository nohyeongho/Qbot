import pandas as pd

try:
    df = pd.read_excel('svclist.xlsx')
    with open('inspect_svclist.txt', 'w', encoding='utf-8') as f:
        f.write("=== Columns ===\n")
        f.write(str(df.columns.tolist()) + "\n")
        f.write("\n=== Data Head ===\n")
        f.write(str(df.head()) + "\n")
        f.write("\n=== Shape ===\n")
        f.write(str(df.shape) + "\n")
except Exception as e:
    with open('inspect_svclist.txt', 'w', encoding='utf-8') as f:
        f.write("Error: " + str(e))
