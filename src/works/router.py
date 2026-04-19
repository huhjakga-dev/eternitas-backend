import uuid
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import WorkStatus
from .service import WorkService
from .models import WorkSession, WorkSessionCrew
from .schema import CreateSession, PrecursorCalculate, MainWorkBody

router = APIRouter(prefix="/works", tags=["Works"])


@router.post("/sessions")
async def create_session(body: CreateSession, db: DbSession) -> dict:
    """
    작업 세션 생성, 참여 승무원은 최대 3명.
    """
    if len(body.crew_ids) > 3:
        raise HTTPException(status_code=422, detail="참여 승무원은 최대 3명입니다.")

    session = WorkSession(cargo_id=uuid.UUID(body.cargo_id), status=WorkStatus.WAITING_PRECURSOR)
    db.add(session)
    db.flush()

    for cid in body.crew_ids:
        db.add(WorkSessionCrew(session_id=session.id, crew_id=uuid.UUID(cid)))

    db.commit()
    return {"id": str(session.id), "status": session.status, "crew_ids": body.crew_ids}


@router.get("/sessions")
async def list_sessions(db: DbSession) -> list[dict]:
    """WorkSession 목록 조회 (최신 20개)."""
    return [
        {"id": str(s.id), "cargo_id": str(s.cargo_id), "status": s.status, "precursor_effect": s.precursor_effect, "created_at": s.created_at}
        for s in db.query(WorkSession).order_by(WorkSession.created_at.desc()).limit(20).all()
    ]


@router.post("/sessions/{session_id}/precursor-calculate")
async def precursor_declaration(session_id: str, body: PrecursorCalculate, db: DbSession) -> dict:
    """
    전조 선언 처리.
    화물/승무원 대항 판정 후 입력 성공 여부와 비교:
    - 둘 다 성공 → SUCCESS (버프 적용)
    - 엇갈림    → INVALID (효과 없음)
    - 둘 다 실패 → FAIL (디버프 적용, 5% 대실패)
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")

    result = WorkService(db).handle_precursor_declaration(
        session,
        uuid.UUID(body.pattern_id),
        uuid.UUID(body.crew_id),
        body.stat,
        body.is_success,
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    db.refresh(session)
    return {
        "session_id": session_id,
        "session_status": session.status,
        "result": result["result"],
        "applied_effect": result["applied_effect"],
        "roll_detail": result["roll_detail"],
        "kill_detail": result["kill_detail"],
    }


@router.post("/sessions/{session_id}/main-work")
async def main_work(session_id: str, body: MainWorkBody, db: DbSession) -> dict:
    """
    본 작업 처리. MAIN_WORK_READY → (사망 시 RESOLVED).
    운영자가 작업 명령 목록을 직접 전달. 턴 판정 → HP 차감 → WorkLog 저장.
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")

    result = WorkService(db).handle_main_work_execution(session, uuid.UUID(body.crew_id), [c.model_dump() for c in body.commands])
    db.refresh(session)
    return {"session_id": session_id, "session_status": session.status, "detail": result}
