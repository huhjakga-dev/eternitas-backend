from fastapi import APIRouter
from src.database import DbSession
from src.runners.models import Crew, CrewStatusEffect
from src.runners.models import Cargo
from src.works.models import WorkSession, WorkSessionCrew, WorkLog, PrecursorLog
from src.reisolation.models import ReIsolationSession, ReIsolationSessionCrew, ReIsolationLog

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/reset/sessions")
async def reset_sessions(db: DbSession) -> dict:
    """
    모든 작업/재격리 세션과 로그를 삭제하고,
    승무원 HP/SP/사망 상태와 화물 집계를 초기값으로 복원.
    """
    # ── 로그 & 세션 삭제 (FK 순서) ──────────────────────────────────────────
    db.query(PrecursorLog).delete(synchronize_session=False)
    db.query(WorkLog).delete(synchronize_session=False)
    db.query(WorkSessionCrew).delete(synchronize_session=False)
    db.query(WorkSession).delete(synchronize_session=False)

    db.query(ReIsolationLog).delete(synchronize_session=False)
    db.query(ReIsolationSessionCrew).delete(synchronize_session=False)
    db.query(ReIsolationSession).delete(synchronize_session=False)

    # ── 승무원 상태이상 해제 ─────────────────────────────────────────────────
    db.query(CrewStatusEffect).delete(synchronize_session=False)

    # ── 승무원 HP/SP/사망 초기화 ─────────────────────────────────────────────
    crews = db.query(Crew).all()
    for crew in crews:
        crew.hp        = crew.max_hp
        crew.sp        = crew.max_sp
        crew.is_dead   = False
        crew.death_time = None

    # ── 화물 집계 초기화 ─────────────────────────────────────────────────────
    cargos = db.query(Cargo).all()
    for cargo in cargos:
        cargo.success_count    = 0
        cargo.failure_count    = 0
        cargo.observation_rate = 0.0
        cargo.is_escaped       = False

    db.commit()

    return {
        "crews_reset":  len(crews),
        "cargos_reset": len(cargos),
        "detail": "세션/로그 삭제 및 승무원·화물 상태 초기화 완료",
    }


@router.post("/reset/crew/{crew_id}")
async def reset_crew(crew_id: str, db: DbSession) -> dict:
    """특정 승무원만 HP/SP/사망/상태이상 초기화."""
    import uuid
    crew = db.query(Crew).filter(Crew.id == uuid.UUID(crew_id)).first()
    if not crew:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="승무원 없음")

    db.query(CrewStatusEffect).filter(CrewStatusEffect.crew_id == crew.id).delete(synchronize_session=False)
    crew.hp         = crew.max_hp
    crew.sp         = crew.max_sp
    crew.is_dead    = False
    crew.death_time = None
    db.commit()

    return {"crew_id": crew_id, "crew_name": crew.crew_name, "hp": crew.hp, "sp": crew.sp}


@router.post("/reset/cargo/{cargo_id}")
async def reset_cargo(cargo_id: str, db: DbSession) -> dict:
    """특정 화물만 집계/탈출 초기화."""
    import uuid
    cargo = db.query(Cargo).filter(Cargo.id == uuid.UUID(cargo_id)).first()
    if not cargo:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="화물 없음")

    cargo.success_count    = 0
    cargo.failure_count    = 0
    cargo.observation_rate = 0.0
    cargo.is_escaped       = False
    db.commit()

    return {"cargo_id": cargo_id, "cargo_name": cargo.cargo_name, "detail": "초기화 완료"}
