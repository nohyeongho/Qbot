from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List

from database import engine, Base, get_db
import models
from fastapi.middleware.cors import CORSMiddleware

# 테이블 생성 확인
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Chatbot Dashboard API")

# 프론트엔드 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    # 이름 중복(동명이인) 방지를 위해 이름과 사번(user_no)을 결합하여 고유 사용자 수를 계산합니다.
    # 의도: 전체 사용자 수는 질문을 하지 않은 사용자(예: INIT만 발생시킨 사용자 등)도 포함되어야 하므로 user_action 필터를 적용하지 않습니다.
    total_users = db.query(
        func.count(func.distinct(models.ChatLog.userName.op('||')('(').op('||')(models.ChatLog.userNo).op('||')(')')))
    ).scalar()
    
    # 의도: 평일(Working Day) 기준 전체 사용자 수를 계산합니다. 주말(0: 일요일, 6: 토요일) 제외.
    total_users_wd = db.query(
        func.count(func.distinct(models.ChatLog.userName.op('||')('(').op('||')(models.ChatLog.userNo).op('||')(')')))
    ).filter(
        func.strftime('%w', models.ChatLog.chatDate).notin_(['0', '6'])
    ).scalar()
    
    # 의도: 비즈니스 요건에 따라 사용자 액션 중 질문('QUESTION')에 해당하는 로그만 총검색건수로 집계합니다.
    total_inquiries = db.query(func.count(models.ChatLog.id)).filter(models.ChatLog.userAction == 'QUESTION').scalar()
    
    # 평일 기준 총검색건수
    total_inquiries_wd = db.query(func.count(models.ChatLog.id))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .filter(func.strftime('%w', models.ChatLog.chatDate).notin_(['0', '6'])).scalar()
    
    # 해결 건수 (SUCCESS 기준)
    # 의도: 질문 중에서 AI봇의 답변이 성공(SUCCESS)적으로 종결된 건수를 파악하기 위해 두 조건을 모두 만족하는 데이터를 조회합니다.
    resolved_count = db.query(func.count(models.ChatLog.id))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .filter(models.ChatLog.aiResultStatus == 'SUCCESS').scalar()
        
    resolve_rate = round(resolved_count / total_inquiries * 100, 1) if total_inquiries > 0 else 0

    # 의도: 대시보드에서 일평균 검색 건수를 동적으로 올바르게 렌더링하기 위해 실제 질문이 발생한 고유 날짜 일수를 계산합니다.
    active_days = db.query(func.count(func.distinct(models.ChatLog.chatDate)))\
        .filter(models.ChatLog.userAction == 'QUESTION').scalar()
        
    # 평일 기준 활성 일수
    active_days_wd = db.query(func.count(func.distinct(models.ChatLog.chatDate)))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .filter(func.strftime('%w', models.ChatLog.chatDate).notin_(['0', '6'])).scalar()

    return {
        "total_users": total_users,
        "total_users_wd": total_users_wd,
        "total_inquiries": total_inquiries,
        "total_inquiries_wd": total_inquiries_wd,
        "resolve_rate": resolve_rate,
        "active_days": active_days,
        "active_days_wd": active_days_wd
    }

@app.get("/api/charts/hourly")
def get_hourly_chart(db: Session = Depends(get_db)):
    # 의도: 시간대별 문의 추이도 실제 질문건수 기준으로 정합성을 맞추기 위해 user_action == 'QUESTION' 필터를 적용합니다.
    results = db.query(models.ChatLog.chatHour, func.count(models.ChatLog.id))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .group_by(models.ChatLog.chatHour).all()
        
    # 0시부터 23시까지 데이터 포맷팅
    hour_dict = {row[0]: row[1] for row in results if row[0] is not None}
    
    labels = []
    data = []
    for h in range(24):
        labels.append(str(h).zfill(2))
        data.append(hour_dict.get(h, 0))
        
    return {"labels": labels, "data": data}

@app.get("/api/charts/types")
def get_types_chart(db: Session = Depends(get_db)):
    # 의도: 문의 유형 분포에서도 실제 질문 로그만 집계하여 총합이 전체 문의건수와 동일하도록 유도합니다.
    results = db.query(models.ChatLog.questionTypeCd, func.count(models.ChatLog.id))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .group_by(models.ChatLog.questionTypeCd).all()
    type_dict = {row[0]: row[1] for row in results}
    
    # 주요 카테고리
    categories = ['UNIFIED_TECH', 'MODEL_SYMPTOM', 'SPEC_INFO']
    labels = ['통합기술', '모델증상', '스펙조회', '기타']
    data = [type_dict.get(cat, 0) for cat in categories]
    
    # 기타 계산
    other = sum(type_dict.values()) - sum(data)
    data.append(other)
    
    return {"labels": labels, "data": data}

@app.get("/api/rankings")
def get_rankings(db: Session = Depends(get_db)):
    # 상위 사용자 10명
    # 이름 중복을 방지하기 위해 사번과 이름을 기준으로 그룹화하고, 차트 라벨에는 '이름(사번)' 포맷으로 제공합니다.
    # 의도: 단순 액션 발생 수가 아닌, 실제 질문 횟수가 많은 다빈도 문의 사용자를 선별하기 위해 user_action == 'QUESTION' 필터를 적용합니다.
    top_users = db.query(
        models.ChatLog.userName,
        models.ChatLog.userNo,
        func.count(models.ChatLog.id).label('count')
    ).filter(models.ChatLog.userAction == 'QUESTION')\
     .group_by(models.ChatLog.userName, models.ChatLog.userNo)\
     .order_by(desc('count')).limit(10).all()
        
    # 상위 센터 10곳
    # 의도: 실제 질문 문의가 가장 많이 집중된 상위 10개 서비스 센터를 분석하기 위해 user_action == 'QUESTION' 필터를 적용합니다.
    top_centers = db.query(models.ChatLog.userDeptName, func.count(models.ChatLog.id).label('count'))\
        .filter(models.ChatLog.userAction == 'QUESTION')\
        .group_by(models.ChatLog.userDeptName)\
        .order_by(desc('count')).limit(10).all()
        
    return {
        "top_users": {
            "labels": [f"{r[0]}({r[1]})" for r in top_users],
            "data": [r[2] for r in top_users]
        },
        "top_centers": {"labels": [r[0] for r in top_centers], "data": [r[1] for r in top_centers]}
    }
