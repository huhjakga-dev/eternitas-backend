import uuid
from sqlalchemy import Column, String, ForeignKey, JSON, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base
from src.common.schema import WorkStatus


class WorkSession(Base):
    __tablename__ = "work_sessions"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_key         = Column(String, unique=True, index=True, nullable=False)
    cargo_id         = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), nullable=False)
    status           = Column(String, default=WorkStatus.WAITING_PRECURSOR)
    precursor_effect = Column(JSON, default=dict)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PrecursorLog(Base):
    __tablename__ = "precursor_logs"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    pattern_id = Column(UUID(as_uuid=True), ForeignKey("cargo_patterns.id"), nullable=True)
    crew_id    = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=True)
    result     = Column(String, nullable=True)  # success / invalid / fail / critical_fail
    created_at = Column(DateTime, server_default=func.now())


class WorkSessionCrew(Base):
    __tablename__ = "work_session_crews"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    crew_id    = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    joined_at  = Column(DateTime, server_default=func.now())


class WorkLog(Base):
    __tablename__ = "work_logs"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id    = Column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), nullable=False)
    crew_id       = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    stat_type     = Column(String)
    planned_count = Column(Integer)
    actual_count  = Column(Integer)
    success_count = Column(Integer)
    damage_taken  = Column(Integer)
    is_interrupted = Column(Boolean, default=False)
    created_at    = Column(DateTime, server_default=func.now())
