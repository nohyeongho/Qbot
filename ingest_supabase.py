import csv
import os
import time
from datetime import datetime
from supabase import create_client, Client

url: str = "https://seanzwnadqaneusqeami.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

def ingest_data_csv(file_path: str):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    # 데이터 중복 방지를 위한 예외 처리 로직 추가
    print("Checking existing records in 'chat_logs'...")
    try:
        res = supabase.table("chat_logs").select("id", count="exact").limit(1).execute()
        if res.count and res.count > 0:
            print(f"경고: 'chat_logs' 테이블에 이미 {res.count}개의 데이터가 존재합니다.")
            print("데이터가 중복해서 삽입되는 것을 방지하기 위해 실행을 취소합니다.")
            print("새로 데이터를 넣으려면 먼저 기존 데이터를 모두 지워주세요. (clear_supabase.py 실행 권장)")
            return
    except Exception as e:
        print(f"데이터 확인 중 오류 발생: {e}")
        return

    print(f"Loading {file_path} in chunks using standard csv module...")

    chunk_size = 500  # 작은 청크 사이즈로 timeout 방지
    total_inserted = 0
    start_time = time.time()
    
    def extract_hour(time_str):
        if not time_str:
            return 0
        try:
            return int(str(time_str).split(':')[0])
        except:
            return 0

    required_cols = ['chatId', 'chatDate', 'chatHour', 'userNo', 'userName', 'userDeptName', 'questionTypeCd', 'aiResultStatus', 'userAction', 'prodLvl2Cd', 'prodLvl2Name', 'prodLvl3Cd', 'prodLvl3Name', 'chatMsg', 'userActionValue']

    with open(file_path, mode='r', encoding='cp949', newline='') as f:
        reader = csv.DictReader(f)
        
        records = []
        for row in reader:
            for col in required_cols:
                if col not in row:
                    row[col] = ''
            
            # fill missing values
            userNo = row.get('userNo') or '알수없음'
            userName = row.get('userName') or '알수없음'
            userDeptName = row.get('userDeptName') or '알수없음'
            questionTypeCd = row.get('questionTypeCd') or '기타'
            aiResultStatus = row.get('aiResultStatus') or '알수없음'
            
            dept_name = userDeptName.replace('서비스센터', '')
            
            chatDate_str = row.get('chatDate')
            chatDate_val = None
            if chatDate_str:
                chatDate_val = chatDate_str[:10]
                    
            record = {
                "chatId": str(row.get('chatId', '')),
                "chatDate": chatDate_val,
                "chatHour": extract_hour(row.get('chatHour')),
                "userNo": userNo,
                "userName": userName,
                "userDeptName": dept_name,
                "questionTypeCd": questionTypeCd,
                "aiResultStatus": aiResultStatus,
                "userAction": row.get('userAction', ''),
                "prodLvl2Cd": row.get('prodLvl2Cd', ''),
                "prodLvl2Name": row.get('prodLvl2Name', ''),
                "prodLvl3Cd": row.get('prodLvl3Cd', ''),
                "prodLvl3Name": row.get('prodLvl3Name', ''),
                "chatMsg": row.get('chatMsg', ''),
                "userActionValue": row.get('userActionValue', '')
            }
            records.append(record)
            
            if len(records) >= chunk_size:
                try:
                    supabase.table("chat_logs").insert(records).execute()
                    total_inserted += len(records)
                    print(f"Inserted {total_inserted} records...")
                except Exception as e:
                    print(f"Error inserting chunk: {e}")
                records = []
                
        # Insert remaining
        if records:
            try:
                supabase.table("chat_logs").insert(records).execute()
                total_inserted += len(records)
                print(f"Inserted {total_inserted} records...")
            except Exception as e:
                print(f"Error inserting final chunk: {e}")

    end_time = time.time()
    print(f"Successfully ingested all {total_inserted} records in {round(end_time - start_time, 1)} seconds!")

if __name__ == "__main__":
    target_csv = "RawData_202605_v1.csv"
    ingest_data_csv(target_csv)
