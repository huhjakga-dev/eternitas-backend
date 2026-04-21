import uuid as _uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import CargoGrade
from src.common.utils import compute_max_caps
from .models import Runner, Crew, Cargo, CargoPattern, Equipment, CrewEquipment, StatusEffect, CrewStatusEffect
from .schema import CreateCrewRunner, CreateCargoRunner, CreateCargoPattern, CreateEquipment, CreateStatusEffect, HpSpDelta

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

    max_hp, max_sp = compute_max_caps(body.health, body.mentality, body.mechanization_lv, body.mechanization_lv)
    crew = Crew(
        runner_id=runner.id,
        crew_name=body.crew_name,
        crew_type=body.crew_type,
        health=body.health, mentality=body.mentality,
        strength=body.strength, inteligence=body.inteligence, luckiness=body.luckiness,
        mechanization_lv=body.mechanization_lv,
        initial_mechanization_lv=body.mechanization_lv,
        max_hp=max_hp, max_sp=max_sp,
        hp=max_hp, sp=max_sp,
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
        total_turns=body.total_turns,
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
    return {"pattern_id": str(pattern.id), "cargo_id": str(pattern.cargo_id), "pattern_name": pattern.pattern_name}


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


@router.post("/equipment")
async def create_equipment(body: CreateEquipment, db: DbSession) -> dict:
    """장비 등록."""
    if db.query(Equipment).filter(Equipment.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"'{body.name}' 장비가 이미 존재합니다.")
    eq = Equipment(
        name=body.name,
        equipment_type=body.equipment_type,
        description=body.description,
        effects=body.effects.model_dump(),
        is_default=body.is_default,
    )
    db.add(eq)
    db.commit()
    return {"equipment_id": str(eq.id), "name": eq.name, "type": eq.equipment_type, "is_default": eq.is_default}


@router.get("/equipment")
async def list_equipment(db: DbSession) -> list[dict]:
    """장비 목록."""
    return [
        {"equipment_id": str(e.id), "name": e.name, "type": e.equipment_type,
         "effects": e.effects, "description": e.description, "is_default": e.is_default}
        for e in db.query(Equipment).order_by(Equipment.is_default.desc(), Equipment.name).all()
    ]


@router.get("/crew")
async def list_crews(db: DbSession) -> list[dict]:
    """등록된 승무원 목록."""
    return [
        {"crew_id": str(c.id), "crew_name": c.crew_name, "hp": c.hp, "sp": c.sp, "is_active": c.is_active, "is_dead": c.is_dead}
        for c in db.query(Crew).all()
    ]


@router.get("/crew/{crew_id}/equipment")
async def get_crew_equipment(crew_id: str, db: DbSession) -> list[dict]:
    """승무원 보유 장비 목록."""
    rows = (
        db.query(CrewEquipment, Equipment)
        .join(Equipment, Equipment.id == CrewEquipment.equipment_id)
        .filter(CrewEquipment.crew_id == _uuid.UUID(crew_id))
        .all()
    )
    return [
        {"crew_equipment_id": str(ce.id), "equipment_id": str(e.id),
         "name": e.name, "type": e.equipment_type, "is_equipped": ce.is_equipped}
        for ce, e in rows
    ]


@router.post("/crew/{crew_id}/equipment")
async def assign_equipment(crew_id: str, equipment_id: str, db: DbSession) -> dict:
    """승무원에게 장비 할당."""
    crew_uuid = _uuid.UUID(crew_id)
    eq_uuid   = _uuid.UUID(equipment_id)

    if not db.query(Crew).filter(Crew.id == crew_uuid).first():
        raise HTTPException(status_code=404, detail="승무원 없음")
    if not db.query(Equipment).filter(Equipment.id == eq_uuid).first():
        raise HTTPException(status_code=404, detail="장비 없음")
    if db.query(CrewEquipment).filter(
        CrewEquipment.crew_id == crew_uuid,
        CrewEquipment.equipment_id == eq_uuid,
    ).first():
        raise HTTPException(status_code=409, detail="이미 보유 중인 장비")

    ce = CrewEquipment(crew_id=crew_uuid, equipment_id=eq_uuid, is_equipped=True)
    db.add(ce)
    db.commit()
    return {"crew_equipment_id": str(ce.id), "crew_id": crew_id, "equipment_id": equipment_id, "is_equipped": True}


@router.patch("/crew/{crew_id}/equipment/{equipment_id}")
async def toggle_equipped(crew_id: str, equipment_id: str, db: DbSession) -> dict:
    """장비 착용/해제 토글."""
    ce = db.query(CrewEquipment).filter(
        CrewEquipment.crew_id == _uuid.UUID(crew_id),
        CrewEquipment.equipment_id == _uuid.UUID(equipment_id),
    ).first()
    if not ce:
        raise HTTPException(status_code=404, detail="해당 승무원의 장비 없음")
    ce.is_equipped = not ce.is_equipped
    db.commit()
    return {"equipment_id": equipment_id, "is_equipped": ce.is_equipped}


@router.delete("/crew/{crew_id}/equipment/{equipment_id}")
async def unassign_equipment(crew_id: str, equipment_id: str, db: DbSession) -> dict:
    """승무원에서 장비 회수."""
    ce = db.query(CrewEquipment).filter(
        CrewEquipment.crew_id == _uuid.UUID(crew_id),
        CrewEquipment.equipment_id == _uuid.UUID(equipment_id),
    ).first()
    if not ce:
        raise HTTPException(status_code=404, detail="해당 승무원의 장비 없음")
    db.delete(ce)
    db.commit()
    return {"detail": "회수 완료"}


@router.get("/cargo")
async def list_cargos(db: DbSession) -> list[dict]:
    """등록된 화물 목록."""
    return [
        {"cargo_id": str(c.id), "cargo_name": c.cargo_name, "grade": c.grade,
         "observation_rate": c.observation_rate, "is_escaped": c.is_escaped}
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


# ── 승무원 상태 관리 ──────────────────────────────────────────────────────────

@router.post("/crew/{crew_id}/kill")
async def instant_kill(crew_id: str, db: DbSession) -> dict:
    """승무원 즉사 처리."""
    crew = db.query(Crew).filter(Crew.id == _uuid.UUID(crew_id)).first()
    if not crew:
        raise HTTPException(status_code=404, detail="승무원 없음")
    crew.hp         = 0
    crew.is_dead    = True
    crew.death_time = datetime.now(timezone.utc)
    db.commit()
    return {"crew_id": crew_id, "crew_name": crew.crew_name, "is_dead": True}


@router.patch("/crew/{crew_id}/hp-sp")
async def adjust_hp_sp(crew_id: str, body: HpSpDelta, db: DbSession) -> dict:
    """승무원 HP/SP 즉시 증감. 양수=회복, 음수=피해. max 초과/0 미만 클램핑."""
    crew = db.query(Crew).filter(Crew.id == _uuid.UUID(crew_id)).first()
    if not crew:
        raise HTTPException(status_code=404, detail="승무원 없음")
    max_hp = crew.max_hp or 1
    max_sp = crew.max_sp or 1
    crew.hp = max(0, min(max_hp, (crew.hp or 0) + body.hp_delta))
    crew.sp = max(0, min(max_sp, (crew.sp or 0) + body.sp_delta))
    db.commit()
    return {"crew_id": crew_id, "crew_name": crew.crew_name,
            "hp": crew.hp, "max_hp": max_hp, "sp": crew.sp, "max_sp": max_sp}


# ── 상태이상 ──────────────────────────────────────────────────────────────────

@router.post("/status-effects")
async def create_status_effect(body: CreateStatusEffect, db: DbSession) -> dict:
    """상태이상 등록."""
    if db.query(StatusEffect).filter(StatusEffect.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"'{body.name}' 상태이상이 이미 존재합니다.")
    se = StatusEffect(name=body.name, description=body.description, stat_json=body.stat_json.model_dump())
    db.add(se)
    db.commit()
    return {"status_effect_id": str(se.id), "name": se.name}


@router.get("/status-effects")
async def list_status_effects(db: DbSession) -> list[dict]:
    """상태이상 목록."""
    return [
        {"status_effect_id": str(se.id), "name": se.name,
         "description": se.description, "stat_json": se.stat_json}
        for se in db.query(StatusEffect).order_by(StatusEffect.name).all()
    ]


@router.get("/crew/{crew_id}/status-effects")
async def get_crew_status_effects(crew_id: str, db: DbSession) -> list[dict]:
    """승무원 적용 중인 상태이상 목록."""
    rows = (
        db.query(CrewStatusEffect, StatusEffect)
        .join(StatusEffect, StatusEffect.id == CrewStatusEffect.status_effect_id)
        .filter(CrewStatusEffect.crew_id == _uuid.UUID(crew_id))
        .all()
    )
    return [
        {"crew_status_effect_id": str(cse.id), "status_effect_id": str(se.id),
         "name": se.name, "stat_json": se.stat_json, "note": cse.note, "applied_at": cse.applied_at}
        for cse, se in rows
    ]


@router.post("/crew/{crew_id}/status-effect")
async def apply_status_effect(crew_id: str, status_effect_id: str, db: DbSession, note: str = None) -> dict:
    """승무원에게 상태이상 적용."""
    crew_uuid = _uuid.UUID(crew_id)
    se_uuid   = _uuid.UUID(status_effect_id)
    if not db.query(Crew).filter(Crew.id == crew_uuid).first():
        raise HTTPException(status_code=404, detail="승무원 없음")
    if not db.query(StatusEffect).filter(StatusEffect.id == se_uuid).first():
        raise HTTPException(status_code=404, detail="상태이상 없음")
    cse = CrewStatusEffect(crew_id=crew_uuid, status_effect_id=se_uuid, note=note)
    db.add(cse)
    db.commit()
    return {"crew_status_effect_id": str(cse.id), "crew_id": crew_id, "status_effect_id": status_effect_id}


@router.delete("/crew/{crew_id}/status-effect/{crew_status_effect_id}")
async def remove_status_effect(crew_id: str, crew_status_effect_id: str, db: DbSession) -> dict:
    """승무원 상태이상 제거."""
    cse = db.query(CrewStatusEffect).filter(
        CrewStatusEffect.id == _uuid.UUID(crew_status_effect_id),
        CrewStatusEffect.crew_id == _uuid.UUID(crew_id),
    ).first()
    if not cse:
        raise HTTPException(status_code=404, detail="해당 상태이상 없음")
    db.delete(cse)
    db.commit()
    return {"detail": "상태이상 제거 완료"}
