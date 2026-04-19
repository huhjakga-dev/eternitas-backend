import uuid as _uuid
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import CargoGrade
from .models import Runner, Crew, Cargo, CargoPattern
from .schema import CreateCrewRunner, CreateCargoRunner, CreateCargoPattern

router = APIRouter(prefix="/runners", tags=["Runners"])

_GRADE_MULT = {
    CargoGrade.STANDARD:     0.1,
    CargoGrade.NON_STANDARD: 0.2,
    CargoGrade.OVERLOAD:     0.3,
    CargoGrade.FIXED:        0.4,
}


@router.post("/crew")
async def create_crew_runner(body: CreateCrewRunner, db: DbSession) -> dict:
    """
    승무원 러너 등록. Runner + Crew 동시 생성.

    Returns: runner_id, crew_id, crew_name
    """
    runner = Runner(user_type="crew")
    db.add(runner)
    db.flush()

    crew = Crew(
        runner_id=runner.id,
        crew_name=body.crew_name,
        crew_type=body.crew_type,
        health=body.health, mentality=body.mentality,
        strength=body.strength, inteligence=body.inteligence, luckiness=body.luckiness,
        hp=body.health * 5, sp=body.mentality * 5,
        mechanization_lv=body.mechanization_lv,
    )
    db.add(crew)
    db.commit()
    db.refresh(crew)
    return {"runner_id": str(runner.id), "crew_id": str(crew.id), "crew_name": crew.crew_name}


@router.post("/cargo")
async def create_cargo_runner(body: CreateCargoRunner, db: DbSession) -> dict:
    """
    화물 러너 등록. Runner + Cargo 동시 생성.

    Returns: runner_id, cargo_id, cargo_name, grade
    """
    runner = Runner(user_type="cargo")
    db.add(runner)
    db.flush()

    cargo = Cargo(
        runner_id=runner.id,
        cargo_name=body.cargo_name, cargo_code=body.cargo_code,
        grade=body.grade, damage_type=body.damage_type,
        health=body.health, mentality=body.mentality,
        strength=body.strength, inteligence=body.inteligence, cause=body.cause,
        damage_multiplier=_GRADE_MULT.get(body.grade, 0.1),
    )
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return {"runner_id": str(runner.id), "cargo_id": str(cargo.id), "cargo_name": cargo.cargo_name, "grade": cargo.grade}


@router.post("/cargo/pattern")
async def upsert_cargo_pattern(body: CreateCargoPattern, db: DbSession) -> dict:
    """
    화물 전조 패턴 등록 (insert)

    Returns: pattern_id, cargo_id, pattern_name, updated(bool)
    """
    try:
        cargo_uuid = _uuid.UUID(body.cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")

    if not db.query(Cargo).filter(Cargo.id == cargo_uuid).first():
        raise HTTPException(status_code=404, detail=f"cargo {body.cargo_id} 없음")

    buff   = body.buff_stat_json.model_dump()
    debuff = body.debuff_stat_json.model_dump()

    pattern = CargoPattern(
        cargo_id=cargo_uuid,
        pattern_name=body.pattern_name, description=body.description, answer=body.answer,
        buff_stat_json=buff, buff_damage_reduction=body.buff_damage_reduction,
        debuff_stat_json=debuff, debuff_demage_increase=body.debuff_demage_increase,
        instant_kill=body.instant_kill,
    )
    db.add(pattern)
    db.commit()
    return {"pattern_id": str(pattern.id), "cargo_id": str(pattern.cargo_id), "pattern_name": pattern.pattern_name, "updated": False}


@router.get("/cargo/{cargo_id}/pattern")
async def get_cargo_pattern(cargo_id: str, db: DbSession) -> dict:
    """화물의 전조 패턴 조회."""
    try:
        cargo_uuid = _uuid.UUID(cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")

    pattern = db.query(CargoPattern).filter(CargoPattern.cargo_id == cargo_uuid).first()
    if not pattern:
        raise HTTPException(status_code=404, detail="패턴 없음")

    return {
        "pattern_id": str(pattern.id), "cargo_id": str(pattern.cargo_id),
        "pattern_name": pattern.pattern_name, "description": pattern.description,
        "buff_stat_json": pattern.buff_stat_json, "buff_damage_reduction": pattern.buff_damage_reduction,
        "debuff_stat_json": pattern.debuff_stat_json, "debuff_demage_increase": pattern.debuff_demage_increase,
        "instant_kill": pattern.instant_kill,
    }


@router.get("/crew")
async def list_crews(db: DbSession) -> list[dict]:
    """등록된 승무원 목록."""
    return [
        {"crew_id": str(c.id), "crew_name": c.crew_name, "hp": c.hp, "sp": c.sp, "is_active": c.is_active, "is_dead": c.is_dead}
        for c in db.query(Crew).all()
    ]


@router.get("/cargo")
async def list_cargos(db: DbSession) -> list[dict]:
    """등록된 화물 목록."""
    return [
        {"cargo_id": str(c.id), "cargo_name": c.cargo_name, "grade": c.grade, "observation_rate": c.observation_rate}
        for c in db.query(Cargo).all()
    ]
