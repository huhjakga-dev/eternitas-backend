from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Float, ForeignKey, JSON
)
from sqlalchemy.sql import func
from src.database import Base


class Runner(Base):
    __tablename__ = "runners"
    id = Column(Integer, primary_key=True)
    band_user_id = Column(String, nullable=False)  # 네이버 밴드 유저 키
    user_type = Column(String)  # 어떤 러너인지 (승무원/화물/운영진 등)
    created_at = Column(DateTime, server_default=func.now())


class Crew(Base):
    __tablename__ = "crews"
    id = Column(Integer, primary_key=True)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False, unique=True)
    crew_name = Column(String, nullable=False)
    health = Column(Integer, default=0)
    mentality = Column(Integer, default=0)
    strength = Column(Integer, default=0)
    inteligence = Column(Integer, default=0)
    luckiness = Column(Integer)
    str = Column(Integer, default=0)
    int = Column(Integer, default=0)
    luc = Column(Integer, default=0)
    mechanization_lv = Column(Integer, default=0)  # 0~5단계
    is_dead = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    death_time = Column(DateTime)  # 부활 시간 계산용
    hp = Column(Integer, default=0)
    sp = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Cargo(Base):
    __tablename__ = "cargos"
    id = Column(Integer, primary_key=True)
    runner_id = Column(Integer, ForeignKey("runners.id"), nullable=False, unique=True)
    cargo_name = Column(String, nullable=False)
    grade = Column(String)  # Standard, Non-Standard, Overload, Fixed
    health = Column(Integer, default=0)
    mentality = Column(Integer, default=0)
    strength = Column(Integer, default=0)
    inteligence = Column(Integer, default=0)
    cause = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    observation_rate = Column(Integer, default=0)  # 20, 60, 100
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class CargoPattern(Base):
    __tablename__ = "cargo_patterns"
    id = Column(Integer, primary_key=True)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False, unique=True)
    pattern_name = Column(String, nullable=False)  # 패턴 명칭 (예: 증기 폭주)
    description = Column(String)  # 패턴 설명 (지문용)

    # 보정치 (정답 시 적용)
    buff_stat_json = Column(JSON, default=dict)  # 작업 시 승무원 스탯 가산치
    damage_reduction = Column(Float, default=0.0)  # 받는 데미지 감소치

    # 페널티 (실패/대실패 시 적용)
    debuff_stat_json = Column(JSON, default=dict)  # 작업 시 승무원 스탯 감산치
    damage_increase = Column(Float, default=0.0)  # 가하는 데미지 증가치
    instant_kill_rate = Column(Float)  # 대실패 시 즉사 판정 확률

    created_at = Column(DateTime, server_default=func.now())


class Equipment(Base):
    __tablename__ = "equipments"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)  # Filter, Weapon, Item
    effects = Column(JSON)  # 보정 스탯 및 특수 효과 (양수/음수/복수지정 가능)
    description = Column(String)
    created_at = Column(DateTime, server_default=func.now())


class CrewEquipment(Base):
    __tablename__ = "crew_equipments"
    id = Column(Integer, primary_key=True)
    crew_id = Column(Integer, ForeignKey("crews.id"), nullable=False)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=False)
    is_equipped = Column(Boolean, default=True)
    acquired_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
