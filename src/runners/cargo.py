import uuid as _uuid
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import CargoGrade
from .models import Cargo, CargoPattern
from .schema import CreateCargoRunner, CreateCargoPattern

router = APIRouter()

_GRADE_MULT = {
    CargoGrade.STANDARD:     0.1,
    CargoGrade.NON_STANDARD: 0.2,
    CargoGrade.OVERLOAD:     0.3,
    CargoGrade.FIXED:        0.4,
}

_GRADE_TURNS = {
    CargoGrade.STANDARD:     5,
    CargoGrade.NON_STANDARD: 7,
    CargoGrade.OVERLOAD:     11,
    CargoGrade.FIXED:        13,
}


@router.post("/cargo")
async def create_cargo(body: CreateCargoRunner, db: DbSession) -> dict:
    """화물 러너 등록. Runner + Cargo 동시 생성."""
    from .models import Runner
    runner = Runner(user_type="cargo")
    db.add(runner)
    db.flush()

    cargo = Cargo(
        runner_id=runner.id,
        cargo_name=body.cargo_name, cargo_code=body.cargo_code,
        grade=body.grade, damage_type=body.damage_type,
        health=body.health, mentality=body.mentality,
        strength=body.strength, inteligence=body.inteligence, cause=body.cause,
        total_turns=_GRADE_TURNS.get(body.grade, 5),
        damage_multiplier=_GRADE_MULT.get(body.grade, 0.1),
    )
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return {"runner_id": str(runner.id), "cargo_id": str(cargo.id),
            "cargo_name": cargo.cargo_name, "grade": cargo.grade}


@router.get("/cargo")
async def list_cargos(db: DbSession) -> list[dict]:
    """등록된 화물 목록."""
    return [
        {"cargo_id": str(c.id), "cargo_name": c.cargo_name, "grade": c.grade,
         "damage_type": c.damage_type, "observation_rate": c.observation_rate, "is_escaped": c.is_escaped}
        for c in db.query(Cargo).all()
    ]


@router.patch("/cargo/{cargo_id}/escape")
async def toggle_cargo_escape(cargo_id: str, db: DbSession) -> dict:
    """화물 탈출 상태 토글."""
    cargo = db.query(Cargo).filter(Cargo.id == _uuid.UUID(cargo_id)).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="화물 없음")
    cargo.is_escaped = not cargo.is_escaped
    db.commit()
    return {"cargo_id": cargo_id, "is_escaped": cargo.is_escaped}


# ── 화물 전조 패턴 ─────────────────────────────────────────────────────────────

@router.post("/cargo/pattern")
async def create_cargo_pattern(body: CreateCargoPattern, db: DbSession) -> dict:
    """화물 전조 패턴 등록."""
    try:
        cargo_uuid = _uuid.UUID(body.cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")

    if not db.query(Cargo).filter(Cargo.id == cargo_uuid).first():
        raise HTTPException(status_code=404, detail=f"cargo {body.cargo_id} 없음")

    pattern = CargoPattern(
        cargo_id=cargo_uuid,
        pattern_name=body.pattern_name, description=body.description, answer=body.answer,
        buff_stat_json=body.buff_stat_json.model_dump(),
        buff_damage_reduction=body.buff_damage_reduction,
        debuff_stat_json=body.debuff_stat_json.model_dump(),
        debuff_demage_increase=body.debuff_demage_increase,
        instant_kill=body.instant_kill,
    )
    db.add(pattern)
    db.commit()
    return {"pattern_id": str(pattern.id), "cargo_id": str(pattern.cargo_id),
            "pattern_name": pattern.pattern_name}


@router.get("/cargo/{cargo_id}/patterns")
async def list_cargo_patterns(cargo_id: str, db: DbSession) -> list[dict]:
    """화물의 전조 패턴 목록."""
    try:
        cargo_uuid = _uuid.UUID(cargo_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="cargo_id가 유효한 UUID가 아닙니다.")
    patterns = db.query(CargoPattern).filter(CargoPattern.cargo_id == cargo_uuid).all()
    return [
        {"pattern_id": str(p.id), "pattern_name": p.pattern_name, "description": p.description}
        for p in patterns
    ]


@router.get("/cargo/{cargo_id}/pattern")
async def get_cargo_pattern(cargo_id: str, db: DbSession) -> dict:
    """화물의 전조 패턴 단건 조회."""
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
