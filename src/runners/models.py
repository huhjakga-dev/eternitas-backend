import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base
from src.common.schema import CargoGrade, CrewType, DamageType, EquipmentType



class Runner(Base):
    """
    러너 테이블
    """
    __tablename__ = "runners"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_type  = Column(String)           # crew / cargo
    created_at = Column(DateTime, server_default=func.now())


class Crew(Base):
    """
    승무원 테이블
    """
    __tablename__ = "crews"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_id        = Column(UUID(as_uuid=True), ForeignKey("runners.id"), nullable=False, unique=True)
    crew_name        = Column(String, nullable=False)
    crew_type        = Column(SQLEnum(CrewType, values_callable=lambda x: [e.value for e in x]), default=CrewType.VOLUNTEER, nullable=False)
    health           = Column(Integer, default=1)
    mentality        = Column(Integer, default=1)
    strength         = Column(Integer, default=1)
    inteligence      = Column(Integer, default=1)
    luckiness        = Column(Integer, default=1)
    mechanization_lv          = Column(Integer, default=0)
    initial_mechanization_lv  = Column(Integer, default=0, nullable=False)
    max_hp                    = Column(Integer)
    max_sp                    = Column(Integer)
    hp         = Column(Integer)
    sp         = Column(Integer)
    token      = Column(Integer, default=0)
    is_dead    = Column(Boolean, default=False) # 사망 여부, True가 되면 한시간 뒤에 부활
    is_active  = Column(Boolean, default=True)
    death_time = Column(DateTime) # 사망시 해당 필드로 부활 시간 측정
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Cargo(Base):
    __tablename__ = "cargos"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    runner_id        = Column(UUID(as_uuid=True), ForeignKey("runners.id"), unique=True)
    cargo_name       = Column(String, nullable=False)
    cargo_code       = Column(String)
    grade            = Column(SQLEnum(CargoGrade, values_callable=lambda x: [e.value for e in x]), nullable=False)
    damage_type      = Column(SQLEnum(DamageType, values_callable=lambda x: [e.value for e in x]), default=DamageType.HP, nullable=False)
    health           = Column(Float, default=0)
    mentality        = Column(Float, default=0)
    strength         = Column(Float, default=0)
    inteligence      = Column(Float, default=0)
    cause            = Column(Float, default=0)
    is_escaped       = Column(Boolean, default=False, nullable=False)
    success_count    = Column(Float, default=0)
    failure_count    = Column(Float, default=0)
    observation_rate  = Column(Float, default=0)   # 관측률
    adapt_point       = Column(Integer, default=0) # 적응 데이터
    total_turns       = Column(Integer, default=10, nullable=False)
    damage_multiplier = Column(Float, default=0.1, nullable=False)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CargoPattern(Base):
    __tablename__ = "cargo_patterns"
    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cargo_id               = Column(UUID(as_uuid=True), ForeignKey("cargos.id"))
    pattern_name           = Column(String)
    description            = Column(String)
    answer                 = Column(String) # 패턴 정답
    buff_stat_json         = Column(JSON)
    buff_damage_reduction  = Column(Float, default=0.0)
    debuff_stat_json       = Column(JSON)
    debuff_demage_increase = Column(Float, default=0.0)
    instant_kill           = Column(Boolean, default=False, nullable=False)
    created_at             = Column(DateTime, server_default=func.now())
    updated_at             = Column(DateTime)


class Equipment(Base):
    __tablename__ = "equipments"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name           = Column(String, nullable=False, unique=True)
    equipment_type = Column(SQLEnum(EquipmentType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    effects        = Column(JSON)
    description    = Column(String)
    is_default     = Column(Boolean, default=False, nullable=False)
    created_at     = Column(DateTime, server_default=func.now())


class CrewEquipment(Base):
    __tablename__ = "crew_equipments"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crew_id      = Column(UUID(as_uuid=True), ForeignKey("crews.id"))
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipments.id"), nullable=False)
    is_equipped  = Column(Boolean, default=True)
    acquired_at  = Column(DateTime, server_default=func.now())
    created_at   = Column(DateTime, server_default=func.now())


class StatusEffect(Base):
    """상태이상 정의 테이블"""
    __tablename__ = "status_effects"
    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                   = Column(String, nullable=False, unique=True)
    description            = Column(String)
    stat_json              = Column(JSON)
    cargo_id               = Column(UUID(as_uuid=True), ForeignKey("cargos.id"), nullable=False)
    tick_damage            = Column(Integer, nullable=True)   # 주기 데미지량
    tick_interval_minutes  = Column(Integer, nullable=True)   # 틱 주기(분)
    duration_minutes       = Column(Integer, nullable=True)   # 지속 시간(분) — 초과 시 자동 해제
    max_ticks              = Column(Integer, nullable=True)   # 최대 틱 횟수 — 초과 시 자동 해제
    created_at             = Column(DateTime, server_default=func.now())


class CrewStatusEffect(Base):
    """승무원에게 적용된 상태이상"""
    __tablename__ = "crew_status_effects"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crew_id          = Column(UUID(as_uuid=True), ForeignKey("crews.id"), nullable=False)
    status_effect_id = Column(UUID(as_uuid=True), ForeignKey("status_effects.id"), nullable=False)
    note             = Column(String)
    applied_at       = Column(DateTime, server_default=func.now())
    expires_at       = Column(DateTime, nullable=True)   # duration_minutes 기준으로 적용 시 계산
    last_tick_at     = Column(DateTime, nullable=True)
    tick_count       = Column(Integer, default=0, nullable=False)
