import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base


class ReIsolationSession(Base):
    __tablename__ = "reisolation_sessions"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cargo_id         = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), nullable=False)
    status           = Column(String, default="active", nullable=False)
    cargo_current_hp = Column(Integer, nullable=False)
    cargo_max_hp     = Column(Integer, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ReIsolationSessionCrew(Base):
    __tablename__ = "reisolation_session_crews"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("reisolation_sessions.id"), nullable=False)
    crew_id    = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    joined_at  = Column(DateTime, server_default=func.now())


class ReisolationPattern(Base):
    """
    재격리 이벤트 패턴. 효과는 JSON 리스트로 저장.
    각 effect: {"type": "instant_kill"|"status_effect"|"damage"|"resolve",
                "target": "random"|"all",
                "status_effect_id": str,  # status_effect 전용
                "amount": int,            # damage 전용
                "damage_type": str}       # damage 전용
    """
    __tablename__ = "reisolation_patterns"
    id                       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cargo_id                 = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), nullable=False)
    pattern_name             = Column(String, nullable=False)
    description              = Column(String)
    stat                     = Column(String, nullable=True)   # None → 주사위 판정 없음
    critical_fail_rate       = Column(Float, default=0.05)
    unconditional_effects    = Column(JSON, default=list)      # 판정 무관 항상 적용
    on_success_effects       = Column(JSON, default=list)
    on_fail_effects          = Column(JSON, default=list)
    on_critical_fail_effects = Column(JSON, default=list)
    created_at               = Column(DateTime, server_default=func.now())


class ReIsolationLog(Base):
    __tablename__ = "reisolation_logs"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id     = Column(UUID(as_uuid=True), ForeignKey("reisolation_sessions.id"), nullable=False)
    crew_id        = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    crew_roll      = Column(Integer)
    hit_bonus      = Column(Integer, default=0)
    final_roll     = Column(Integer)
    threshold      = Column(Integer)
    success        = Column(Boolean)
    damage_dealt   = Column(Integer, default=0)
    counter_damage = Column(Integer, default=0)
    created_at     = Column(DateTime, server_default=func.now())
