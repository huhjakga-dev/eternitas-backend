import uuid as _uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.utils import compute_max_caps, roll_solo, roll_vs_crew
from .models import Crew, Equipment, CrewEquipment, StatusEffect, CrewStatusEffect
from .schema import CreateCrewRunner, HpSpDelta, RollAppealBody, RollVsRunnerBody

router = APIRouter()


@router.post("/crew")
async def create_crew(body: CreateCrewRunner, db: DbSession) -> dict:
    """승무원 러너 등록. Runner + Crew 동시 생성."""
    from .models import Runner
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


@router.get("/crew")
async def list_crews(db: DbSession) -> list[dict]:
    """등록된 승무원 목록."""
    return [
        {"crew_id": str(c.id), "crew_name": c.crew_name, "hp": c.hp, "sp": c.sp,
         "is_active": c.is_active, "is_dead": c.is_dead, "token": c.token or 0}
        for c in db.query(Crew).all()
    ]


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


@router.patch("/crew/{crew_id}/token")
async def adjust_token(crew_id: str, delta: int, db: DbSession) -> dict:
    """승무원 토큰 증감. 양수=지급, 음수=차감. 0 미만 클램핑."""
    crew = db.query(Crew).filter(Crew.id == _uuid.UUID(crew_id)).first()
    if not crew:
        raise HTTPException(status_code=404, detail="승무원 없음")
    crew.token = max(0, (crew.token or 0) + delta)
    db.commit()
    return {"crew_id": crew_id, "crew_name": crew.crew_name, "token": crew.token}


# ── 판정 ─────────────────────────────────────────────────────────────────────

@router.post("/crew/roll/appeal")
async def roll_appeal(body: RollAppealBody, db: DbSession) -> dict:
    """캐릭터 어필: 1d(stat×5) vs 고정 성공치. 이상이면 성공."""
    crew = db.query(Crew).filter(Crew.id == _uuid.UUID(body.crew_id)).first()
    if not crew:
        raise HTTPException(status_code=404, detail="승무원 없음")
    stat_val = int(getattr(crew, body.stat, 1) or 1)
    result   = roll_solo(stat_val, body.threshold)
    return {
        "crew_name": crew.crew_name,
        "stat":      body.stat,
        "dice":      f"1d{stat_val * 5}",
        "roll":      result["roll"],
        "threshold": body.threshold,
        "success":   result["success"],
    }


@router.post("/crew/roll/vs-runner")
async def roll_vs_runner(body: RollVsRunnerBody, db: DbSession) -> dict:
    """러너 대항: 각 스탯으로 1d(stat×5) 굴려 높은 쪽 승리. 데미지 없음."""
    crew_a = db.query(Crew).filter(Crew.id == _uuid.UUID(body.crew_a_id)).first()
    crew_b = db.query(Crew).filter(Crew.id == _uuid.UUID(body.crew_b_id)).first()
    if not crew_a or not crew_b:
        raise HTTPException(status_code=404, detail="승무원 없음")
    stat_a  = int(getattr(crew_a, body.stat, 1) or 1)
    stat_b  = int(getattr(crew_b, body.stat, 1) or 1)
    result  = roll_vs_crew(stat_a, stat_b)
    winner  = crew_a.crew_name if result["a_wins"] else crew_b.crew_name
    return {
        "crew_a":    crew_a.crew_name,
        "stat_a":    body.stat,
        "dice_a":    f"1d{stat_a * 5}",
        "roll_a":    result["roll_a"],
        "crew_b":    crew_b.crew_name,
        "stat_b":    body.stat,
        "dice_b":    f"1d{stat_b * 5}",
        "roll_b":    result["roll_b"],
        "winner":    winner,
        "a_wins":    result["a_wins"],
    }


# ── 승무원 장비 ───────────────────────────────────────────────────────────────

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


# ── 승무원 상태이상 ────────────────────────────────────────────────────────────

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
        {
            "crew_status_effect_id": str(cse.id),
            "status_effect_id":      str(se.id),
            "name":                  se.name,
            "stat_json":             se.stat_json,
            "note":                  cse.note,
            "applied_at":            cse.applied_at,
            "expires_at":            cse.expires_at,
            "tick_count":            cse.tick_count,
            "max_ticks":             se.max_ticks,
            "tick_interval_minutes": se.tick_interval_minutes,
        }
        for cse, se in rows
    ]


@router.post("/crew/{crew_id}/status-effect")
async def apply_status_effect(crew_id: str, status_effect_id: str, db: DbSession, note: str = None) -> dict:
    """승무원에게 상태이상 적용."""
    crew_uuid = _uuid.UUID(crew_id)
    se_uuid   = _uuid.UUID(status_effect_id)
    if not db.query(Crew).filter(Crew.id == crew_uuid).first():
        raise HTTPException(status_code=404, detail="승무원 없음")
    se = db.query(StatusEffect).filter(StatusEffect.id == se_uuid).first()
    if not se:
        raise HTTPException(status_code=404, detail="상태이상 없음")

    now        = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=se.duration_minutes)) if se.duration_minutes else None

    cse = CrewStatusEffect(
        crew_id=crew_uuid, status_effect_id=se_uuid,
        note=note, expires_at=expires_at, tick_count=0,
    )
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
