import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Enum as SQLEnum, Computed
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base
from src.common.schema import CargoGrade


class Runner(Base):
    __tablename__ = "runners"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    band_user_id = Column(String)
    user_type = Column(String)  # crew / cargo / admin
    created_at = Column(DateTime, server_default=func.now())


class Crew(Base):
    __tablename__ = "crews"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_id = Column(UUID(as_uuid=True), ForeignKey("runners.id"), nullable=False, unique=True)
    crew_name = Column(String, nullable=False)
    health = Column(Integer, default=1)         # 1~10, hp = health * 5
    mentality = Column(Integer, default=1)      # 1~10, sp = mentality * 5
    strength = Column(Integer, default=1)       # 1~10, 작업 스탯: STR
    inteligence = Column(Integer, default=1)    # 1~10, 작업 스탯: INT (DB 오타 그대로)
    luckiness = Column(Integer, default=1)      # 1~10, 작업 스탯: LUC
    mechanization_lv = Column(Integer, default=0)
    is_dead = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    death_time = Column(DateTime)
    max_hp = Column(Integer, Computed(
        "ROUND((health * 5) * CASE mechanization_lv "
        "WHEN 2 THEN 1.1 WHEN 3 THEN 1.3 WHEN 4 THEN 1.5 ELSE 1.0 END)",
        persisted=True
    ))
    max_sp = Column(Integer, Computed(
        "ROUND((mentality * 5) * CASE mechanization_lv "
        "WHEN 2 THEN 0.8 WHEN 3 THEN 0.6 WHEN 4 THEN 0.5 ELSE 1.0 END)",
        persisted=True
    ))
    hp = Column(Integer)                        # 현재 HP, 트리거로 초기화 및 클램핑
    sp = Column(Integer)                        # 현재 SP, 트리거로 초기화 및 클램핑
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Cargo(Base):
    __tablename__ = "cargos"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_id = Column(UUID(as_uuid=True), ForeignKey("runners.id"), unique=True)
    cargo_name = Column(String, nullable=False)
    grade = Column(SQLEnum(CargoGrade, values_callable=lambda x: [e.value for e in x]), nullable=False)
    health = Column(Float, default=0)
    mentality = Column(Float, default=0)
    strength = Column(Float, default=0)
    inteligence = Column(Float, default=0)
    cause = Column(Float, default=0)
    success_count = Column(Float, default=0)
    failure_count = Column(Float, default=0)
    observation_rate = Column(Float, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CargoPattern(Base):
    __tablename__ = "cargo_patterns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cargo_id = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), unique=True)
    pattern_name = Column(String)
    description = Column(String)  # 전조 선언 시 시스템이 게시하는 댓글 내용
    answer = Column(String)       # 정답 대응 (LLM 판정 기준)
    buff_stat_json = Column(JSON)
    buff_damage_reduction = Column(Float, default=0.0)
    debuff_stat_json = Column(JSON)
    debuff_demage_increase = Column(Float, default=0.0)
    instant_kill_rate = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime)


class Equipment(Base):
    __tablename__ = "equipments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    equipment_type = Column(String)
    effects = Column(JSON)
    description = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class CrewEquipment(Base):
    __tablename__ = "crew_equipments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crew_id = Column(UUID(as_uuid=True), ForeignKey("crews.id"))
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipments.id"), nullable=False)
    is_equipped = Column(Boolean, default=True)
    acquired_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
