import pandas as pd
import os
import math
from supabase import create_client, Client
import time

# Supabase 연결 정보 (기존 ingest_supabase.py 참고)
url: str = "https://seanzwnadqaneusqeami.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlYW56d25hZHFhbmV1c3FlYW1pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODEzNzMxNjIsImV4cCI6MjA5Njk0OTE2Mn0.3-R97YJzSsVW2ecJSW5briUFwFVNAATJHhASB3xgNuI"
supabase: Client = create_client(url, key)

def ingest_svclist(file_path: str):
    """
    svclist.xlsx 파일을 읽어 Supabase의 sm_svclist 테이블에 업로드하는 함수
    - 파일이 존재하는지 검증
    - NaN 값을 안전하게 처리
    - 청크(chunk) 단위로 데이터 업로드
    """
    if not os.path.exists(file_path):
        print(f"오류: {file_path} 파일을 찾을 수 없습니다.")
        return

    print(f"{file_path} 파일 읽는 중...")
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"엑셀 파일 읽기 실패: {e}")
        return

    # NaN 데이터를 처리하기 쉽게 변경
    # 부서나 센터명 등의 텍스트 데이터가 빈 경우 기본값 할당
    df['담당명(원소속)'] = df['담당명(원소속)'].fillna('알수없음')
    df['모센터명(처리)'] = df['모센터명(처리)'].fillna('알수없음')
    df['처리일자_년월'] = df['처리일자_년월'].fillna('')
    df['수리기사ID(SM)'] = df['수리기사ID(SM)'].fillna('')
    df['수리기사명(SM)'] = df['수리기사명(SM)'].fillna('알수없음')

    # 숫자 컬럼(01~31일)의 NaN 값을 0 또는 None으로 처리
    # 수파베이스 NUMERIC 컬럼에 맞도록 처리하기 위해 None 처리
    day_columns = [f"{i:02d}" for i in range(1, 32)]
    
    records = []
    print("데이터 변환 중...")
    for _, row in df.iterrows():
        # 기본 정보 매핑
        record = {
            "dept_name": str(row['담당명(원소속)']),
            "center_name": str(row['모센터명(처리)']),
            "process_ym": str(row['처리일자_년월']),
            "sm_id": str(row['수리기사ID(SM)']),
            "sm_name": str(row['수리기사명(SM)']),
        }
        
        # 1일~31일 데이터 매핑 (NaN인 경우 None으로 치환하여 DB에서 null 처리)
        for day_col in day_columns:
            val = row.get(day_col)
            # 숫자가 아니거나 NaN일 경우 None으로 설정
            if pd.isna(val):
                record[f"day_{day_col}"] = None
            else:
                record[f"day_{day_col}"] = float(val)

        records.append(record)

    # 기존 데이터 초기화 (월별 데이터 중복을 막기 위해 전체를 갱신하거나 필요한 경우만 남김)
    # 현재는 전체 업데이트 성격이므로 데이터를 모두 지우고 다시 삽입
    try:
        print("기존 sm_svclist 데이터 삭제 중...")
        # id가 0보다 큰 모든 데이터 삭제 (전체 삭제 트릭)
        supabase.table("sm_svclist").delete().gt("id", -1).execute()
    except Exception as e:
        print(f"기존 데이터 삭제 경고(처음 실행이거나 비어있을 수 있음): {e}")

    # 대량 Insert 시 청크(chunk) 단위로 나누어 업로드 (Supabase 권장 방식)
    chunk_size = 1000
    print(f"총 {len(records)} 건의 데이터를 {chunk_size} 건씩 업로드합니다...")
    
    start_time = time.time()
    for i in range(0, len(records), chunk_size):
        chunk = records[i:i + chunk_size]
        try:
            supabase.table("sm_svclist").insert(chunk).execute()
            print(f"업로드 진행 중: {i + len(chunk)} / {len(records)} 건 완료")
        except Exception as e:
            print(f"데이터 업로드 중 오류 발생 (Chunk {i}): {e}")
            break
            
    end_time = time.time()
    print(f"모든 데이터 업로드 완료! (소요 시간: {round(end_time - start_time, 1)} 초)")

if __name__ == "__main__":
    target_excel = "svclist.xlsx"
    ingest_svclist(target_excel)
