import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Depends

# .env 파일에서 환경 변수 로드
load_dotenv()


def connect_db():
    global db_conn

    # Supabase 연결 정보 (환경 변수에서 가져옴)
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    create_engine(
        SQLALCHEMY_DATABASE_URL, pool_size=10, max_overflow=20, pool_pre_ping=True
    )
    return db_conn


# 종속성 주입(DI)용 함수: API 핸들러에서 DB 세션을 사용할 때 호출
def get_db():
    with Session(bind=db_conn) as session:
        try:
            yield session
        finally:
            session.close()


DbSession = Annotated[Session, Depends(get_db)]
