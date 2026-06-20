import pandas as pd
import os
from supabase import create_client, Client
import time

url: str = "https://seanzwnadqaneusqeami.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

def ingest_sm_job(file_path: str):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    print(f"Loading {file_path}...")
    df = pd.read_excel(file_path)

    # NaN 값 처리
    df = df.fillna('')

    # DB에 삽입할 딕셔너리 리스트 생성
    records = []
    for _, row in df.iterrows():
        # 수리기사ID(SM)가 없는 경우 스킵
        if str(row['수리기사ID(SM)']).strip() == '':
            continue
            
        record = {
            "sm_id": str(row['수리기사ID(SM)']),
            "name": str(row['이름']),
            "team_name": str(row['팀명(원소속)']),
            "parent_center_name": str(row['모센터명(원소속)']),
            "center_name": str(row['센터명(원소속)']),
            "parent_center_name_1": str(row['모센터명(원소속).1']),
            "job_title": str(row['직무'])
        }
        records.append(record)

    # 이전 데이터 초기화 (전체 삭제)
    try:
        print("Clearing existing sm_job data...")
        # primary key is sm_id, we can just delete where sm_id != ''
        supabase.table("sm_job").delete().neq("sm_id", "").execute()
    except Exception as e:
        print(f"Delete warning (might be empty or restricted): {e}")

    # Chunk insert
    chunk_size = 5000
    print(f"Inserting {len(records)} records in chunks of {chunk_size}...")
    
    start_time = time.time()
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            supabase.table("sm_job").upsert(chunk).execute()
            print(f"Inserted {i + len(chunk)} / {len(records)} records...")
        except Exception as e:
            print(f"Error inserting chunk {i}: {e}")
            break
            
    end_time = time.time()
    print(f"Successfully ingested all records in {round(end_time - start_time, 1)} seconds!")

if __name__ == "__main__":
    target_excel = "SM_직무.xlsx"
    ingest_sm_job(target_excel)
