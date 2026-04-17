from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from annotated_types import Ge, Le
from typing import Annotated

from src.database import DbSession
from src.common.schema import CargoGrade, CrewType
from .models import Runner, Crew, Cargo, CargoPattern

router = APIRouter(prefix="/runners", tags=["Runners"])

Stat = Annotated[int, Ge(1), Le(10)]  # 1~10 정수


# ------------------------------------------------------------------ #
# Request Body 스키마
# ------------------------------------------------------------------ #

class CreateCrewRunner(BaseModel):
    band_user_id: str
    crew_name: str
    crew_type: CrewType = CrewType.VOLUNTEER
    # 5개 스탯: 각 1~10, 합계 25 이하
    # hp = health * 5, sp = mentality * 5 (자동 계산)
    health: Stat = 1
    mentality: Stat = 1
    strength: Stat = 1
    inteligence: Stat = 1
    luckiness: Stat = 1
    mechanization_lv: int = 0

    @model_validator(mode="after")
    def check_stat_sum(self):
        total = self.health + self.mentality + self.strength + self.inteligence + self.luckiness
        if total > 25:
            raise ValueError(f"스탯 합계가 25를 초과할 수 없습니다. (현재: {total})")
        return self


class CreateCargoRunner(BaseModel):
    band_user_id: str
    cargo_name: str
    cargo_code: Optional[str] = None
    grade: CargoGrade
    # 5개 스탯: 각 1~10, 합계 25 이하
    health: Stat = 1
    mentality: Stat = 1
    strength: Stat = 1
    inteligence: Stat = 1
    cause: Stat = 1

    @model_validator(mode="after")
    def check_stat_sum(self):
        total = self.health + self.mentality + self.strength + self.inteligence + self.cause
        if total > 25:
            raise ValueError(f"스탯 합계가 25를 초과할 수 없습니다. (현재: {total})")
        return self


class StatModifier(BaseModel):
    """승무원 스탯 보정치. 양수=버프, 음수=디버프"""
    strength: float = 0.0      # 근력
    inteligence: float = 0.0   # 지력
    luckiness: float = 0.0     # 행운
    health: float = 0.0            # 최대 HP 보정
    mentality: float = 0.0            # 최대 SP 보정


class CreateCargoPattern(BaseModel):
    cargo_id: str                       # cargos.id (UUID)
    pattern_name: str
    description: Optional[str] = None  # 전조 선언 시 시스템이 게시하는 댓글 내용
    answer: Optional[str] = None       # 정답 대응 (LLM 판정 기준)

    # 성공 시 보정치
    buff_stat_json: StatModifier = StatModifier()
    buff_damage_reduction: float = 0.0      # 받는 데미지 감소율 (0.0 ~ 1.0)

    # 실패/대실패 시 패널티
    debuff_stat_json: StatModifier = StatModifier()
    debuff_demage_increase: float = 0.0     # 받는 데미지 증가율 (0.0 ~ 1.0)
    instant_kill_rate: Optional[float] = None  # 대실패 즉사 확률 (0.0 ~ 1.0)


# ------------------------------------------------------------------ #
# 러너 등록
# ------------------------------------------------------------------ #

@router.post("/crew")
async def create_crew_runner(body: CreateCrewRunner, db: DbSession):
    """승무원 러너 등록 (Runner + Crew 동시 생성)"""
    exists = db.query(Runner).filter(
        Runner.band_user_id == body.band_user_id,
        Runner.user_type == "crew"
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"이미 등록된 승무원 러너: {body.band_user_id}")

    runner = Runner(band_user_id=body.band_user_id, user_type="crew")
    db.add(runner)
    db.flush()

    crew = Crew(
        runner_id=runner.id,
        crew_name=body.crew_name,
        crew_type=body.crew_type,
        health=body.health,
        mentality=body.mentality,
        strength=body.strength,
        inteligence=body.inteligence,
        luckiness=body.luckiness,
        hp=body.health * 5,
        sp=body.mentality * 5,
        mechanization_lv=body.mechanization_lv,
    )
    db.add(crew)
    db.commit()
    db.refresh(runner)
    db.refresh(crew)

    return {
        "runner_id": str(runner.id),
        "crew_id": str(crew.id),
        "crew_name": crew.crew_name,
        "band_user_id": runner.band_user_id,
    }


@router.post("/cargo")
async def create_cargo_runner(body: CreateCargoRunner, db: DbSession):
    """화물 러너 등록 (Runner + Cargo 동시 생성)"""
    exists = db.query(Runner).filter(
        Runner.band_user_id == body.band_user_id,
        Runner.user_type == "cargo"
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail=f"이미 등록된 화물 러너: {body.band_user_id}")

    runner = Runner(band_user_id=body.band_user_id, user_type="cargo")
    db.add(runner)
    db.flush()

    cargo = Cargo(
        runner_id=runner.id,
        cargo_name=body.cargo_name,
        cargo_code=body.cargo_code,
        grade=body.grade,
        health=body.health,
        mentality=body.mentality,
        strength=body.strength,
        inteligence=body.inteligence,
        cause=body.cause,
    )
    db.add(cargo)
    db.commit()
    db.refresh(runner)
    db.refresh(cargo)

    return {
        "runner_id": str(runner.id),
        "cargo_id": str(cargo.id),
        "cargo_name": cargo.cargo_name,
        "grade": cargo.grade,
        "band_user_id": runner.band_user_id,
    }


# ------------------------------------------------------------------ #
# 전조 패턴 등록
# ------------------------------------------------------------------ #

@router.post("/cargo/pattern")
async def create_cargo_pattern(body: CreateCargoPattern, db: DbSession):
    """
    화물 전조 패턴 등록.
    cargo_id 1개당 패턴 1개 (unique). 이미 있으면 덮어씀(upsert).
    """
    import uuid as _uuid
    try:
        cargo_uuid = _uuid.UUID(body.cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")

    cargo = db.query(Cargo).filter(Cargo.id == cargo_uuid).first()
    if not cargo:
        raise HTTPException(status_code=404, detail=f"cargo {body.cargo_id} 없음")

    buff_dict = body.buff_stat_json.model_dump()
    debuff_dict = body.debuff_stat_json.model_dump()

    existing = db.query(CargoPattern).filter(CargoPattern.cargo_id == cargo_uuid).first()
    if existing:
        # upsert
        existing.pattern_name = body.pattern_name
        existing.description = body.description
        existing.answer = body.answer
        existing.buff_stat_json = buff_dict
        existing.buff_damage_reduction = body.buff_damage_reduction
        existing.debuff_stat_json = debuff_dict
        existing.debuff_demage_increase = body.debuff_demage_increase
        existing.instant_kill_rate = body.instant_kill_rate
        db.commit()
        db.refresh(existing)
        return {
            "pattern_id": str(existing.id),
            "cargo_id": str(existing.cargo_id),
            "pattern_name": existing.pattern_name,
            "updated": True,
        }

    pattern = CargoPattern(
        cargo_id=cargo_uuid,
        pattern_name=body.pattern_name,
        description=body.description,
        answer=body.answer,
        buff_stat_json=buff_dict,
        buff_damage_reduction=body.buff_damage_reduction,
        debuff_stat_json=debuff_dict,
        debuff_demage_increase=body.debuff_demage_increase,
        instant_kill_rate=body.instant_kill_rate,
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)

    return {
        "pattern_id": str(pattern.id),
        "cargo_id": str(pattern.cargo_id),
        "pattern_name": pattern.pattern_name,
        "updated": False,
    }


@router.get("/cargo/{cargo_id}/pattern")
async def get_cargo_pattern(cargo_id: str, db: DbSession):
    """화물의 전조 패턴 조회"""
    import uuid as _uuid
    try:
        cargo_uuid = _uuid.UUID(cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")

    pattern = db.query(CargoPattern).filter(CargoPattern.cargo_id == cargo_uuid).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="패턴 없음")

    return {
        "pattern_id": str(pattern.id),
        "cargo_id": str(pattern.cargo_id),
        "pattern_name": pattern.pattern_name,
        "description": pattern.description,
        "buff_stat_json": pattern.buff_stat_json,
        "buff_damage_reduction": pattern.buff_damage_reduction,
        "debuff_stat_json": pattern.debuff_stat_json,
        "debuff_demage_increase": pattern.debuff_demage_increase,
        "instant_kill_rate": pattern.instant_kill_rate,
    }


# ------------------------------------------------------------------ #
# 목록 조회
# ------------------------------------------------------------------ #

@router.get("/crew")
async def list_crews(db: DbSession):
    """등록된 승무원 목록"""
    crews = db.query(Crew).all()
    return [
        {
            "crew_id": str(c.id),
            "runner_id": str(c.runner_id),
            "crew_name": c.crew_name,
            "hp": c.hp,
            "sp": c.sp,
            "is_active": c.is_active,
            "is_dead": c.is_dead,
        }
        for c in crews
    ]


@router.get("/cargo")
async def list_cargos(db: DbSession):
    """등록된 화물 목록"""
    cargos = db.query(Cargo).all()
    return [
        {
            "cargo_id": str(c.id),
            "runner_id": str(c.runner_id),
            "cargo_name": c.cargo_name,
            "grade": c.grade,
            "observation_rate": c.observation_rate,
        }
        for c in cargos
    ]
