import uuid as _uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
from src.database import DbSession
from src.common.schema import CargoGrade
from .models import Cargo, CargoPattern, CargoGimmick
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
        {"cargo_id": str(c.id), "cargo_name": c.cargo_name, "cargo_code": c.cargo_code,
         "grade": c.grade, "damage_type": c.damage_type, "observation_rate": c.observation_rate,
         "is_escaped": c.is_escaped, "total_turns": c.total_turns}
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
        {"pattern_id": str(p.id), "pattern_name": p.pattern_name,
         "description": p.description, "answer": p.answer}
        for p in patterns
    ]


# ── 화물 기믹 ──────────────────────────────────────────────────────────────────

class CreateGimmick(BaseModel):
    name:             str
    description:      Optional[str] = None
    action_type:      Literal["kill_if_stat", "apply_damage", "apply_status_effect"]
    stat:             Optional[str] = None
    operator:         Optional[Literal["lte", "lt", "gte", "gt", "eq"]] = None
    threshold:        Optional[int] = None
    amount:           Optional[int] = None
    damage_type:      Optional[str] = None
    damage_calc:      Optional[Literal["fixed", "percent_hp", "percent_sp"]] = "fixed"
    status_effect_id: Optional[str] = None
    pattern_id:       Optional[str] = None
    sort_order:       int = 0


@router.post("/cargo/{cargo_id}/gimmicks")
async def create_gimmick(cargo_id: str, body: CreateGimmick, db: DbSession) -> dict:
    """화물 특수 기믹 등록."""
    cargo_uuid = _uuid.UUID(cargo_id)
    if not db.query(Cargo).filter(Cargo.id == cargo_uuid).first():
        raise HTTPException(status_code=404, detail="화물 없음")

    g = CargoGimmick(
        cargo_id         = cargo_uuid,
        name             = body.name,
        description      = body.description,
        action_type      = body.action_type,
        stat             = body.stat,
        operator         = body.operator,
        threshold        = body.threshold,
        amount           = body.amount,
        damage_type      = body.damage_type,
        damage_calc      = body.damage_calc or "fixed",
        status_effect_id = _uuid.UUID(body.status_effect_id) if body.status_effect_id else None,
        pattern_id       = _uuid.UUID(body.pattern_id) if body.pattern_id else None,
        sort_order       = body.sort_order,
    )
    db.add(g)
    db.commit()
    return {"gimmick_id": str(g.id), "name": g.name}


@router.get("/cargo/{cargo_id}/gimmicks")
async def list_gimmicks(cargo_id: str, db: DbSession, pattern_id: Optional[str] = None) -> list[dict]:
    """화물 기믹 목록 (sort_order 순). pattern_id 전달 시 해당 패턴에 연결된 기믹만 반환."""
    q = db.query(CargoGimmick).filter(CargoGimmick.cargo_id == _uuid.UUID(cargo_id))
    if pattern_id:
        q = q.filter(CargoGimmick.pattern_id == _uuid.UUID(pattern_id))
    gimmicks = q.order_by(CargoGimmick.sort_order).all()
    return [
        {
            "gimmick_id":       str(g.id),
            "name":             g.name,
            "description":      g.description,
            "action_type":      g.action_type,
            "stat":             g.stat,
            "operator":         g.operator,
            "threshold":        g.threshold,
            "amount":           g.amount,
            "damage_type":      g.damage_type,
            "damage_calc":      g.damage_calc or "fixed",
            "status_effect_id": str(g.status_effect_id) if g.status_effect_id else None,
            "pattern_id":       str(g.pattern_id) if g.pattern_id else None,
            "sort_order":       g.sort_order,
        }
        for g in gimmicks
    ]


@router.delete("/cargo/{cargo_id}/gimmicks/{gimmick_id}")
async def delete_gimmick(cargo_id: str, gimmick_id: str, db: DbSession) -> dict:
    """기믹 삭제."""
    g = db.query(CargoGimmick).filter(
        CargoGimmick.id == _uuid.UUID(gimmick_id),
        CargoGimmick.cargo_id == _uuid.UUID(cargo_id),
    ).first()
    if not g:
        raise HTTPException(status_code=404, detail="기믹 없음")
    db.delete(g)
    db.commit()
    return {"detail": "삭제 완료"}


