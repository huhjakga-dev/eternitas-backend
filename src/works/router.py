from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid

from src.database import DbSession
from src.common.schema import WorkStatus
from .service import WorkService
from .worker import work_polling_worker
from .models import WorkSession, WorkSessionCrew

router = APIRouter(prefix="/works", tags=["Works"])


# ------------------------------------------------------------------ #
# 운영 엔드포인트
# ------------------------------------------------------------------ #

@router.post("/collect")
async def collect_today_works(db: DbSession):
    """오늘 [작업] 게시글을 세션으로 등록"""
    service = WorkService(db)
    new_sessions = await service.collect_today_works()
    return {"registered": len(new_sessions)}


@router.post("/polling")
async def trigger_polling():
    """폴링 워커 수동 실행"""
    await work_polling_worker()
    return {"message": "폴링 완료"}


# ------------------------------------------------------------------ #
# 테스트용 공통 스키마
# ------------------------------------------------------------------ #

class FakeComment(BaseModel):
    comment_key: str = "test_comment_key"
    content: str
    # 밴드 유저 키 대신 crew_id / cargo_id 직접 지정 가능
    band_user_id: Optional[str] = None   # 실제 밴드 유저 키 (Runner 테이블 기준)
    crew_id: Optional[str] = None        # crews.id (UUID) 직접 지정
    cargo_id: Optional[str] = None       # cargos.id (UUID) 직접 지정


# ------------------------------------------------------------------ #
# 테스트 엔드포인트
# ------------------------------------------------------------------ #

class CreateTestSession(BaseModel):
    cargo_id: str
    post_key: str = "test_post_key"
    crew_ids: list[str] = []   # 참여 승무원 UUID 목록 (최대 3명)


@router.post("/test/sessions", tags=["Test"])
async def create_test_session(body: CreateTestSession, db: DbSession):
    """
    테스트용 WorkSession 직접 생성.
    crew_ids: 참여 승무원 ID 목록 (최대 3명, DB 트리거로 강제)
    """
    if len(body.crew_ids) > 3:
        raise HTTPException(status_code=422, detail="참여 승무원은 최대 3명입니다.")

    exists = db.query(WorkSession).filter(WorkSession.post_key == body.post_key).first()
    if exists:
        return {"id": str(exists.id), "message": "이미 존재함", "status": exists.status}

    session = WorkSession(
        post_key=body.post_key,
        cargo_id=uuid.UUID(body.cargo_id),
        status=WorkStatus.WAITING_PRECURSOR,
    )
    db.add(session)
    db.flush()  # session.id 확보

    for crew_id_str in body.crew_ids:
        db.add(WorkSessionCrew(
            session_id=session.id,
            crew_id=uuid.UUID(crew_id_str),
        ))

    db.commit()
    db.refresh(session)
    return {
        "id": str(session.id),
        "post_key": session.post_key,
        "status": session.status,
        "crew_ids": body.crew_ids,
    }


@router.get("/test/sessions", tags=["Test"])
async def list_sessions(db: DbSession):
    """현재 DB의 WorkSession 목록 (최신 20개)"""
    sessions = db.query(WorkSession).order_by(WorkSession.created_at.desc()).limit(20).all()
    return [
        {
            "id": str(s.id),
            "post_key": s.post_key,
            "cargo_id": str(s.cargo_id),
            "status": s.status,
            "precursor_effect": s.precursor_effect,
            "created_at": s.created_at,
        }
        for s in sessions
    ]


@router.post("/test/precursor-declaration/{session_id}", tags=["Test"])
async def test_precursor_declaration(session_id: str, body: FakeComment, db: DbSession):
    """
    [선언] 처리 테스트.

    session_id: work_sessions.id (UUID)

    Args:
        comment_key: 댓글 id
        content: 댓글 내용
        band_user_id: 밴드 유저 id (Runner 테이블 기준)

    Returns:
        
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session {session_id} 없음")

    service = WorkService(db)
    comment = {
        "comment_key": body.comment_key,
        "content": body.content,
        "author": {"cargo_id": body.band_user_id or "test_user"},
    }
    await service.handle_precursor_declaration(session, comment)
    db.refresh(session)
    return {"session_id": str(session.id), "session_status": session.status}


@router.post("/test/crew-response/{session_id}", tags=["Test"])
async def test_crew_response(session_id: str, body: FakeComment, db: DbSession):
    """
    [대응] 처리 테스트.
    session이 PRECURSOR_ACTIVE 상태여야 함.
    band_user_id 또는 crew_id 중 하나 필요.
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session {session_id} 없음")

    # crew_id가 직접 주어지면 comment author로 band_user_id 대신 사용
    author_key = body.band_user_id or (f"__crew_id__{body.crew_id}" if body.crew_id else "test_user")

    service = WorkService(db)
    comment = {
        "comment_key": body.comment_key,
        "content": body.content,
        "author": {"user_key": author_key},
    }
    await service.handle_crew_response(session, comment)
    db.refresh(session)
    return {
        "session_id": str(session.id),
        "session_status": session.status,
        "precursor_effect": session.precursor_effect,
    }


@router.post("/test/main-work/{session_id}", tags=["Test"])
async def test_main_work(session_id: str, body: FakeComment, db: DbSession):
    """
    [작업] 처리 테스트.
    session이 MAIN_WORK_READY 상태여야 함.
    band_user_id 또는 crew_id 중 하나 필요.
    """
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"session {session_id} 없음")

    author_key = body.band_user_id or (f"__crew_id__{body.crew_id}" if body.crew_id else "test_user")

    service = WorkService(db)
    comment = {
        "comment_key": body.comment_key,
        "content": body.content,
        "author": {"user_key": author_key},
    }
    await service.handle_main_work_execution(session, comment)
    db.refresh(session)
    return {"session_id": str(session.id), "session_status": session.status}


@router.post("/test/parse-commands", tags=["Test"])
async def test_parse_commands(body: FakeComment, db: DbSession):
    """LLM 작업 명령 파싱 테스트. 예: content = '체력 5회 지력 3회'"""
    service = WorkService(db)
    result = await service._parse_work_commands(body.content)
    return {"parsed": result}


@router.post("/test/judge-success", tags=["Test"])
async def test_judge_success(pattern_id: str, body: FakeComment, db: DbSession):
    """LLM 대응 성패 판정 테스트."""
    service = WorkService(db)
    result = await service._judge_success(uuid.UUID(pattern_id), body.content)
    return {"result": result}
