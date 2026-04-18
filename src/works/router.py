import uuid
from fastapi import APIRouter, HTTPException
from src.database import DbSession
from src.common.schema import WorkStatus
from .service import WorkService
from .models import WorkSession, WorkSessionCrew
from .schema import CreateSession, CrewResponseBody, MainWorkBody

router = APIRouter(prefix="/works", tags=["Works"])


@router.post("/sessions")
async def create_session(body: CreateSession, db: DbSession) -> dict:
    """
    작업 세션 생성. post_key 중복이면 기존 세션 반환.
    참여 승무원은 최대 3명.
    """
    if len(body.crew_ids) > 3:
        raise HTTPException(status_code=422, detail="참여 승무원은 최대 3명입니다.")

    exists = db.query(WorkSession).filter(WorkSession.post_key == body.post_key).first()
    if exists:
        return {"id": str(exists.id), "status": exists.status, "message": "이미 존재함"}

    session = WorkSession(post_key=body.post_key, cargo_id=uuid.UUID(body.cargo_id), status=WorkStatus.WAITING_PRECURSOR)
    db.add(session)
    db.flush()

    for cid in body.crew_ids:
        db.add(WorkSessionCrew(session_id=session.id, crew_id=uuid.UUID(cid)))

    db.commit()
    return {"id": str(session.id), "post_key": session.post_key, "status": session.status, "crew_ids": body.crew_ids}


@router.get("/sessions")
async def list_sessions(db: DbSession) -> list[dict]:
    """WorkSession 목록 조회 (최신 20개)."""
    return [
        {"id": str(s.id), "post_key": s.post_key, "cargo_id": str(s.cargo_id), "status": s.status, "precursor_effect": s.precursor_effect, "created_at": s.created_at}
        for s in db.query(WorkSession).order_by(WorkSession.created_at.desc()).limit(20).all()
    ]


@router.post("/sessions/{session_id}/precursor-declaration")
async def precursor_declaration(session_id: str, db: DbSession) -> dict:
    """
    전조 선언 처리. WAITING_PRECURSOR → PRECURSOR_ACTIVE.
    화물 패턴을 찾아 PrecursorLog 생성.
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")

    result = WorkService(db).handle_precursor_declaration(session)
    db.refresh(session)
    return {"session_id": session_id, "session_status": session.status, "detail": result}


@router.post("/sessions/{session_id}/crew-response")
async def crew_response(session_id: str, body: CrewResponseBody, db: DbSession) -> dict:
    """
    승무원 대응 처리. PRECURSOR_ACTIVE → MAIN_WORK_READY.
    운영자가 결정한 판정 결과(success/invalid/fail/critical_fail)로 버프/디버프 저장.
    critical_fail이면 승무원 즉시 사망.
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")

    result = WorkService(db).handle_crew_response(session, uuid.UUID(body.crew_id), body.result)
    db.refresh(session)
    return {"session_id": session_id, "session_status": session.status, "precursor_effect": session.precursor_effect, "detail": result}


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
