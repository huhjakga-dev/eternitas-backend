import uuid as _uuid
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import ReIsolationStatus
from .models import ReIsolationSession, ReIsolationSessionCrew
from .schema import CreateReIsolationSession, ReIsolationAttack
from .service import ReIsolationService, crew_vs_crew_combat

router = APIRouter(prefix="/reisolation", tags=["ReIsolation"])


@router.post("/sessions")
async def create_session(body: CreateReIsolationSession, db: DbSession) -> dict:
    """재격리 세션 생성. 화물이 is_escaped=True 상태여야 함."""
    result = ReIsolationService(db).create_session(
        _uuid.UUID(body.cargo_id),
        [_uuid.UUID(cid) for cid in body.crew_ids],
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/sessions")
async def list_sessions(db: DbSession) -> list[dict]:
    """재격리 세션 목록 (최신 20개)."""
    rows = (
        db.query(ReIsolationSession)
        .order_by(ReIsolationSession.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for s in rows:
        crew_ids = [
            str(sc.crew_id) for sc in
            db.query(ReIsolationSessionCrew)
            .filter(ReIsolationSessionCrew.session_id == s.id).all()
        ]
        result.append({
            "session_id":       str(s.id),
            "cargo_id":         str(s.cargo_id),
            "status":           s.status,
            "cargo_current_hp": s.cargo_current_hp,
            "cargo_max_hp":     s.cargo_max_hp,
            "crew_ids":         crew_ids,
            "created_at":       s.created_at,
        })
    return result


@router.post("/sessions/{session_id}/attack")
async def attack(session_id: str, body: ReIsolationAttack, db: DbSession) -> dict:
    """승무원 1명 공격 판정 + 화물 반격."""
    session = db.query(ReIsolationSession).filter(
        ReIsolationSession.id == _uuid.UUID(session_id)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")

    result = ReIsolationService(db).execute_attack(session, _uuid.UUID(body.crew_id))
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/crew-combat")
async def crew_combat(crew_a_id: str, crew_b_id: str, db: DbSession) -> dict:
    """승무원 vs 승무원 전투. 행운 + 무기 보정 대항."""
    result = crew_vs_crew_combat(db, _uuid.UUID(crew_a_id), _uuid.UUID(crew_b_id))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
