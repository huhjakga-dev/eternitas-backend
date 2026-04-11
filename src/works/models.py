import uuid
from sqlalchemy import Column, String, ForeignKey, JSON, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base
from src.common.schema import WorkStatus


class WorkSession(Base):
    __tablename__ = "work_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_key = Column(String, unique=True, index=True, nullable=False)
    cargo_id = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), nullable=False)
    status = Column(String, default=WorkStatus.WAITING_PRECURSOR)
    precursor_effect = Column(JSON, default=dict)
    observation_added_percentage = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PrecursorLog(Base):
    __tablename__ = "precursor_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("cargo_patterns.id"), nullable=True)
    crew_id = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=True)
    result = Column(String, nullable=True)  # success / fail / critical_fail
    declaration_comment_id = Column(String)
    response_comment_id = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class WorkSessionCrew(Base):
    """세션 참여 승무원 (최대 3명, DB 트리거로 강제)"""
    __tablename__ = "work_session_crews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    crew_id = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    joined_at = Column(DateTime, server_default=func.now())


class WorkLog(Base):
    __tablename__ = "work_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    crew_id = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    stat_type = Column(String)
    planned_count = Column(Integer)
    actual_count = Column(Integer)
    success_count = Column(Integer)
    damage_taken = Column(Integer)
    damage_type = Column(String)  # hp / sp / both
    is_interrupted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
