from fastapi import APIRouter
from src.database import DbSession
from .models import TrainState

router = APIRouter(prefix="/train", tags=["Train"])

_STATUS_MAP = {
    "정속": lambda s: 60 <= s <= 64,
    "과속": lambda s: s >= 65,
    "저속": lambda s: s <= 59,
}


def _speed_status(speed: int) -> str:
    for label, check in _STATUS_MAP.items():
        if check(speed):
            return label
    return "정속"


@router.get("/state")
async def get_train_state(db: DbSession) -> dict:
    """현재 열차 속력 및 상태 조회."""
    state = db.query(TrainState).first()
    if not state:
        return {"speed": 60, "status": "정속", "unit": "Mph"}
    return {
        "speed":  state.speed,
        "status": _speed_status(state.speed),
        "unit":   "Mph",
    }
