import sqlite3
import pandas as pd
conn = sqlite3.connect('dashboard.db')
df = pd.read_sql("SELECT center_name, count(*) as c FROM chat_logs c JOIN sm_job s ON c.userNo = s.sm_id WHERE userAction='QUESTION' AND job_title='출장' GROUP BY center_name ORDER BY c DESC LIMIT 10;", conn)
print(df)
