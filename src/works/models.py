from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from src.database import Base
from src.common.schema import DamageType, WorkStatus


class WorkSession(Base):
    __tablename__ = "work_sessions"
    id = Column(Integer, primary_key=True)
    post_key = Column(String, unique=True, index=True, nullable=False)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)
    # waiting_precursor → precursor_active → main_work_ready → resolved
    status = Column(String, default=WorkStatus.WAITING_PRECURSOR)
    precursor_effect = Column(JSON, default=dict)  # 전조 결과 보정치 캐싱
    observation_added_percentage = Column(Integer, default=0)  # 관측률 상승치
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PrecursorLog(Base):
    __tablename__ = "precursor_logs"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("work_sessions.id"), nullable=False)
    pattern_id = Column(Integer, ForeignKey("cargo_patterns.id"), nullable=True)
    crew_id = Column(Integer, ForeignKey("crews.id"), nullable=True)
    result = Column(String, nullable=True)  # success, fail, critical_fail
    declaration_comment_id = Column(String)  # 화물의 선언 댓글 ID (중복 방지용)
    response_comment_id = Column(String)  # 승무원의 대응 댓글 ID
    created_at = Column(DateTime, server_default=func.now())


class WorkLog(Base):
    __tablename__ = "work_logs"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("work_sessions.id"), nullable=False)
    crew_id = Column(Integer, ForeignKey("crews.id"), nullable=False)
    stat_type = Column(String)  # 어떤 스탯으로 작업 시도했는지
    planned_count = Column(Integer)   # 유저가 선언한 횟수
    actual_count = Column(Integer)    # 실제 진행된 횟수
    success_count = Column(Integer)   # 그 중 성공한 횟수
    damage_taken = Column(Integer)    # 데미지 총량
    damage_type = Column(SQLEnum(DamageType))  # hp / sp / both
    is_interrupted = Column(Boolean, default=False)  # 작업 도중 사망 등으로 중단 여부
    created_at = Column(DateTime, server_default=func.now())
