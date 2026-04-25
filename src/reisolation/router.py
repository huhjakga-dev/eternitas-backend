import uuid as _uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from src.database import DbSession
from src.common.schema import ReIsolationStatus
from src.runners.models import Cargo, Crew
from .models import ReIsolationSession, ReIsolationSessionCrew, ReisolationPattern
from .schema import CreateReIsolationSession, ReIsolationAttack, CreateReisolationPattern, ApplyPatternBody
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


@router.post("/patterns")
async def create_pattern(body: CreateReisolationPattern, db: DbSession) -> dict:
    """재격리 패턴 생성."""
    from src.runners.models import Cargo
    cargo = db.query(Cargo).filter(Cargo.id == _uuid.UUID(body.cargo_id)).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="화물 없음")

    pattern = ReisolationPattern(
        cargo_id=_uuid.UUID(body.cargo_id),
        pattern_name=body.pattern_name,
        description=body.description,
        stat=body.stat,
        critical_fail_rate=body.critical_fail_rate,
        unconditional_effects=[e.model_dump(exclude_none=True) for e in body.unconditional_effects],
        on_success_effects=[e.model_dump(exclude_none=True) for e in body.on_success_effects],
        on_fail_effects=[e.model_dump(exclude_none=True) for e in body.on_fail_effects],
        on_critical_fail_effects=[e.model_dump(exclude_none=True) for e in body.on_critical_fail_effects],
    )
    db.add(pattern)
    db.commit()
    db.refresh(pattern)
    return {"pattern_id": str(pattern.id), "pattern_name": pattern.pattern_name}


@router.get("/cargo/{cargo_id}/patterns")
async def list_patterns(cargo_id: str, db: DbSession) -> list[dict]:
    """화물의 재격리 패턴 목록."""
    patterns = (
        db.query(ReisolationPattern)
        .filter(ReisolationPattern.cargo_id == _uuid.UUID(cargo_id))
        .all()
    )
    return [
        {
            "pattern_id":              str(p.id),
            "pattern_name":            p.pattern_name,
            "description":             p.description,
            "stat":                    p.stat,
            "critical_fail_rate":      p.critical_fail_rate,
            "unconditional_effects":   p.unconditional_effects,
            "on_success_effects":      p.on_success_effects,
            "on_fail_effects":         p.on_fail_effects,
            "on_critical_fail_effects": p.on_critical_fail_effects,
        }
        for p in patterns
    ]


@router.post("/sessions/{session_id}/apply-pattern")
async def apply_pattern(session_id: str, body: ApplyPatternBody, db: DbSession) -> dict:
    """재격리 패턴 적용 (주사위 판정 + 대응지문 판정 + 효과 적용)."""
    session = db.query(ReIsolationSession).filter(
        ReIsolationSession.id == _uuid.UUID(session_id)
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")

    result = ReIsolationService(db).apply_pattern(
        session,
        _uuid.UUID(body.pattern_id),
        [_uuid.UUID(cid) for cid in body.crew_ids],
        body.stat,
        body.response_success,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class CargoPatternBody(BaseModel):
    session_id:       str
    crew_ids:         list[str] = []
    stat:             Optional[str]  = None
    response_success: Optional[bool] = None


@router.post("/cargo/{cargo_id}/pattern/{pattern_id}")
async def cargo_pattern(
    cargo_id: str, pattern_id: str, body: CargoPatternBody, db: DbSession
) -> dict:
    """
    화물·패턴별 재격리 패턴 실행. 화물에 등록된 서비스 클래스로 디스패치.
    등록된 서비스가 없으면 DB 패턴 기반 범용 처리.
    """
    from src.reisolation.services.registry import get_reisolation_service

    session = db.query(ReIsolationSession).filter(ReIsolationSession.id == _uuid.UUID(body.session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="세션 없음")
    if session.status == ReIsolationStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="이미 종료된 세션")

    cargo = db.query(Cargo).filter(Cargo.id == _uuid.UUID(cargo_id)).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="화물 없음")

    service_class = get_reisolation_service(cargo.cargo_name)
    service       = service_class(db, session, cargo)
    result        = service.run_pattern(
        _uuid.UUID(pattern_id),
        [_uuid.UUID(cid) for cid in body.crew_ids],
        body.stat,
        body.response_success,
    )

    db.commit()
    db.refresh(session)

    return {
        **result,
        "log_text":       "\n".join(result.get("log", [])),
        "session_status": session.status,
    }


@router.post("/crew-combat")
async def crew_combat(crew_a_id: str, crew_b_id: str, db: DbSession) -> dict:
    """승무원 vs 승무원 전투. 행운 + 무기 보정 대항."""
    result = crew_vs_crew_combat(db, _uuid.UUID(crew_a_id), _uuid.UUID(crew_b_id))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
