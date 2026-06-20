import csv
import os
import time
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models
from datetime import datetime

# 기존 테이블 구조가 다를 경우를 대비해 재생성
try:
    models.ChatLog.__table__.drop(engine, checkfirst=True)
except:
    pass
Base.metadata.create_all(bind=engine)

def ingest_data_csv(file_path: str):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    print(f"Loading {file_path} in chunks using standard csv module...")

    db = SessionLocal()
    chunk_size = 5000
    total_inserted = 0
    start_time = time.time()
    
    def extract_hour(time_str):
        if not time_str:
            return 0
        try:
            return int(str(time_str).split(':')[0])
        except:
            return 0

    required_cols = ['chatId', 'chatDate', 'chatHour', 'userName', 'userNo', 'userDeptName', 'questionTypeCd', 'aiResultStatus', 'userAction', 'prodLvl2Cd', 'prodLvl2Name', 'prodLvl3Cd', 'prodLvl3Name']

    with open(file_path, mode='r', encoding='cp949', newline='') as f:
        reader = csv.DictReader(f)
        
        # Check missing columns
        fieldnames = reader.fieldnames or []
        
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
                try:
                    chatDate_val = datetime.strptime(chatDate_str[:10], '%Y-%m-%d').date()
                except:
                    pass
                    
            record = models.ChatLog(
                chatId=str(row.get('chatId', '')),
                chatDate=chatDate_val,
                chatHour=extract_hour(row.get('chatHour')),
                userName=userName,
                userNo=userNo,
                userDeptName=dept_name,
                questionTypeCd=questionTypeCd,
                aiResultStatus=aiResultStatus,
                userAction=row.get('userAction', ''),
                prodLvl2Cd=row.get('prodLvl2Cd', ''),
                prodLvl2Name=row.get('prodLvl2Name', ''),
                prodLvl3Cd=row.get('prodLvl3Cd', ''),
                prodLvl3Name=row.get('prodLvl3Name', '')
            )
            records.append(record)
            
            if len(records) >= chunk_size:
                try:
                    db.bulk_save_objects(records)
                    db.commit()
                    total_inserted += len(records)
                    print(f"Inserted {total_inserted} records...")
                except Exception as e:
                    print(f"Error inserting chunk: {e}")
                    db.rollback()
                    break
                records = []
                
        # Insert remaining
        if records:
            try:
                db.bulk_save_objects(records)
                db.commit()
                total_inserted += len(records)
                print(f"Inserted {total_inserted} records...")
            except Exception as e:
                print(f"Error inserting final chunk: {e}")
                db.rollback()

    db.close()
    end_time = time.time()
    print(f"Successfully ingested all {total_inserted} records in {round(end_time - start_time, 1)} seconds!")

if __name__ == "__main__":
    target_csv = "RawData_202605_v1.csv"
    ingest_data_csv(target_csv)
