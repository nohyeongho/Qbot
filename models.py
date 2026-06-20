from sqlalchemy import Column, Integer, String, Date, Time, Float
from database import Base

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chatId = Column(String, index=True)
    chatDate = Column(Date, index=True)
    chatHour = Column(Integer, index=True) # 추출된 시간대 (0-23)
    userName = Column(String, index=True)
    userNo = Column(String, index=True) # 중복 사용자(동명이인) 구분을 위한 사번 필드 추가
    userDeptName = Column(String, index=True)
    questionTypeCd = Column(String, index=True)
    aiResultStatus = Column(String, index=True)
    userAction = Column(String)
    prodLvl2Cd = Column(String)
    prodLvl2Name = Column(String)
    prodLvl3Cd = Column(String)
    prodLvl3Name = Column(String)
