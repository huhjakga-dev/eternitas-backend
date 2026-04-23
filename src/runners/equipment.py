from fastapi import APIRouter, HTTPException
from src.database import DbSession
from .models import Equipment
from .schema import CreateEquipment

router = APIRouter()


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
