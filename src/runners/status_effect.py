from fastapi import APIRouter, HTTPException
from src.database import DbSession
from .models import StatusEffect
from .schema import CreateStatusEffect

router = APIRouter()


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
