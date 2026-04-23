import uuid as _uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from .models import StatusEffect, CrewStatusEffect, Cargo
from .schema import CreateStatusEffect

router = APIRouter()


@router.post("/status-effects")
async def create_status_effect(body: CreateStatusEffect, db: DbSession) -> dict:
    """상태이상 등록."""
    if db.query(StatusEffect).filter(StatusEffect.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"'{body.name}' 상태이상이 이미 존재합니다.")

    cargo_uuid = _uuid.UUID(body.cargo_id)
    if not db.query(Cargo).filter(Cargo.id == cargo_uuid).first():
        raise HTTPException(status_code=404, detail="화물 없음")

    se = StatusEffect(
        name=body.name,
        description=body.description,
        stat_json=body.stat_json.model_dump(),
        cargo_id=cargo_uuid,
        tick_damage=body.tick_damage,
        tick_interval_minutes=body.tick_interval_minutes,
        duration_minutes=body.duration_minutes,
        max_ticks=body.max_ticks,
    )
    db.add(se)
    db.commit()
    return {"status_effect_id": str(se.id), "name": se.name}


@router.get("/status-effects")
async def list_status_effects(db: DbSession) -> list[dict]:
    """상태이상 목록."""
    return [
        {
            "status_effect_id":      str(se.id),
            "name":                  se.name,
            "description":           se.description,
            "stat_json":             se.stat_json,
            "cargo_id":              str(se.cargo_id),
            "tick_damage":           se.tick_damage,
            "tick_interval_minutes": se.tick_interval_minutes,
            "duration_minutes":      se.duration_minutes,
            "max_ticks":             se.max_ticks,
        }
        for se in db.query(StatusEffect).order_by(StatusEffect.name).all()
    ]
