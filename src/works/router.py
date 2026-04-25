import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional
from src.database import DbSession
from src.common.schema import WorkStatus, DamageType
from src.runners.models import Cargo, CargoGimmick, Crew, CrewStatusEffect, StatusEffect
from src.common.utils import compute_max_caps
from .service import WorkService
from .models import WorkSession, WorkSessionCrew, WorkLog
from .schema import CreateSession, PrecursorCalculate, MainWorkBody

router = APIRouter(prefix="/works", tags=["Works"])


class ForceCompleteBody(BaseModel):
    result: Literal["success", "fail"]


class CargoPrecursorBody(BaseModel):
    session_id: str
    crew_id:    str
    result:     Literal["success", "fail", "critical_fail"]


@router.post("/cargo/{cargo_id}/precursor/{pattern_id}")
async def cargo_precursor(
    cargo_id: str, pattern_id: str, body: CargoPrecursorBody, db: DbSession
) -> dict:
    """
    화물·패턴별 전조 실행. 화물에 등록된 서비스 클래스로 디스패치.
    등록된 서비스가 없으면 DB 패턴 기반 범용 처리.
    """
    from src.works.services.registry import get_cargo_service

    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(body.session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")
    if session.status == WorkStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="이미 종료된 세션")

    cargo = db.query(Cargo).filter(Cargo.id == uuid.UUID(cargo_id)).first()
    if not cargo:
        raise HTTPException(status_code=404, detail="화물 없음")

    crew = db.query(Crew).filter(Crew.id == uuid.UUID(body.crew_id)).first()
    if not crew:
        raise HTTPException(status_code=404, detail="승무원 없음")

    service_class = get_cargo_service(cargo.cargo_name)
    service       = service_class(db, session, cargo)
    result        = service.run_precursor(uuid.UUID(pattern_id), body.result, crew)

    db.commit()
    db.refresh(session)

    return {
        **result,
        "log_text":       "\n".join(result.get("log", [])),
        "session_status": session.status,
    }


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
    if session.status == WorkStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="이미 종료된 세션입니다.")
    if session.status == WorkStatus.WAITING_PRECURSOR:
        raise HTTPException(status_code=400, detail="전조 판정이 완료되지 않은 세션입니다.")

    result = WorkService(db).handle_main_work_execution(
        session, uuid.UUID(body.crew_id), [c.model_dump() for c in body.commands]
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    db.refresh(session)
    return {
        "session_id":      session_id,
        "session_status":  session.status,
        "summary":         result.get("summary", []),
        "damage_per_crew": result.get("damage_per_crew", {}),
        "session_result":  result.get("session_result"),
        "interrupted":     result.get("interrupted", False),
    }


@router.post("/sessions/{session_id}/force-complete")
async def force_complete(session_id: str, body: ForceCompleteBody, db: DbSession) -> dict:
    """작업 세션 강제 종료. 화물 총 턴수 기준으로 전체 성공/실패 처리."""
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")
    if session.status == WorkStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="이미 종료된 세션입니다.")

    cargo       = db.query(Cargo).filter(Cargo.id == session.cargo_id).first()
    total_turns = (cargo.total_turns or 1) if cargo else 1
    is_success  = body.result == "success"

    # 참여 승무원 중 첫 번째 생존자를 대표 crew_id로 WorkLog 기록
    from src.runners.models import Crew
    from src.common.schema import DamageType
    crew_ids = [sc.crew_id for sc in db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()]
    rep_crew = next(
        (c for c in db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if not c.is_dead),
        None,
    ) if crew_ids else None

    if rep_crew:
        db.add(WorkLog(
            session_id=session.id,
            crew_id=rep_crew.id,
            stat_type="health",
            planned_count=total_turns,
            actual_count=total_turns,
            success_count=total_turns if is_success else 0,
            damage_taken=0,
            damage_type=DamageType.HP,
            is_interrupted=False,
        ))

    session.status       = WorkStatus.RESOLVED
    session.final_result = body.result

    if cargo:
        if is_success:
            cargo.success_count    = (cargo.success_count or 0) + 1
            cargo.observation_rate = min(100.0, (cargo.observation_rate or 0.0) + 10.0)
        else:
            cargo.failure_count = (cargo.failure_count or 0) + 1

    db.commit()
    return {
        "session_id":    session_id,
        "final_result":  body.result,
        "total_turns":   total_turns,
        "success_turns": total_turns if is_success else 0,
        "cargo_observation_rate": cargo.observation_rate if cargo else None,
    }


class RunGimmickBody(BaseModel):
    gimmick_id: str


@router.post("/sessions/{session_id}/run-gimmick")
async def run_gimmick(session_id: str, body: RunGimmickBody, db: DbSession) -> dict:
    """화물 특수 기믹 실행. 세션 참여 승무원 전체에 적용."""
    session = db.query(WorkSession).filter(WorkSession.id == uuid.UUID(session_id)).first()
    if not session:
        raise HTTPException(status_code=404, detail="session 없음")

    gimmick = db.query(CargoGimmick).filter(CargoGimmick.id == uuid.UUID(body.gimmick_id)).first()
    if not gimmick:
        raise HTTPException(status_code=404, detail="기믹 없음")

    crew_ids = [sc.crew_id for sc in db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()]
    crews: list[Crew] = db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []
    alive = [c for c in crews if not c.is_dead]

    affected: list[str] = []
    log_lines: list[str] = []

    _OP_MAP = {"lte": lambda a, b: a <= b, "lt": lambda a, b: a < b,
               "gte": lambda a, b: a >= b, "gt": lambda a, b: a > b, "eq": lambda a, b: a == b}
    _OP_KO  = {"lte": "이하", "lt": "미만", "gte": "이상", "gt": "초과", "eq": "동일"}

    if gimmick.action_type == "kill_if_stat":
        op_fn = _OP_MAP.get(gimmick.operator, lambda a, b: a <= b)
        for crew in alive:
            val = int(getattr(crew, gimmick.stat, 0) or 0)
            if op_fn(val, gimmick.threshold):
                crew.hp = 0
                crew.is_dead = True
                crew.death_time = datetime.now(timezone.utc)
                affected.append(crew.crew_name)
                log_lines.append(f"{crew.crew_name} ({gimmick.stat}={val}) — 즉사")
            else:
                log_lines.append(f"{crew.crew_name} ({gimmick.stat}={val}) — 생존")

    elif gimmick.action_type == "apply_damage":
        dmg_type  = DamageType(gimmick.damage_type) if gimmick.damage_type else DamageType.HP
        dmg_calc  = gimmick.damage_calc or "fixed"
        for crew in alive:
            if dmg_calc == "percent_hp":
                amount = max(1, round((crew.max_hp or crew.hp or 0) * gimmick.amount / 100))
                label  = f"최대HP {gimmick.amount}%({amount})"
            elif dmg_calc == "percent_sp":
                amount = max(1, round((crew.max_sp or crew.sp or 0) * gimmick.amount / 100))
                label  = f"최대SP {gimmick.amount}%({amount})"
            else:
                amount = gimmick.amount
                label  = str(amount)

            if dmg_type == DamageType.HP:
                crew.hp = max(0, (crew.hp or 0) - amount)
                if crew.hp <= 0 and not crew.is_dead:
                    crew.is_dead = True
                    crew.death_time = datetime.now(timezone.utc)
                    log_lines.append(f"{crew.crew_name} — HP {label} 피해 → 사망")
                else:
                    log_lines.append(f"{crew.crew_name} — HP {label} 피해 (잔여 {crew.hp})")
            elif dmg_type == DamageType.SP:
                crew.sp = max(0, (crew.sp or 0) - amount)
                log_lines.append(f"{crew.crew_name} — SP {label} 피해 (잔여 {crew.sp})")
            else:  # BOTH
                h = amount // 2
                s = amount - h
                crew.hp = max(0, (crew.hp or 0) - h)
                crew.sp = max(0, (crew.sp or 0) - s)
                if crew.hp <= 0 and not crew.is_dead:
                    crew.is_dead = True
                    crew.death_time = datetime.now(timezone.utc)
                    log_lines.append(f"{crew.crew_name} — HP -{h} / SP -{s} → 사망")
                else:
                    log_lines.append(f"{crew.crew_name} — HP -{h} (잔여 {crew.hp}) / SP -{s} (잔여 {crew.sp})")
            affected.append(crew.crew_name)

    elif gimmick.action_type == "apply_status_effect":
        se = db.query(StatusEffect).filter(StatusEffect.id == gimmick.status_effect_id).first()
        if not se:
            raise HTTPException(status_code=404, detail="상태이상 없음")
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        for crew in alive:
            already = db.query(CrewStatusEffect).filter(
                CrewStatusEffect.crew_id == crew.id,
                CrewStatusEffect.status_effect_id == se.id,
            ).first()
            if already:
                log_lines.append(f"{crew.crew_name} — 이미 적용 중 (스킵)")
                continue
            expires_at = (now + timedelta(minutes=se.duration_minutes)) if se.duration_minutes else None
            db.add(CrewStatusEffect(
                crew_id=crew.id, status_effect_id=se.id,
                expires_at=expires_at, tick_count=0,
            ))
            affected.append(crew.crew_name)
            log_lines.append(f"{crew.crew_name} — '{se.name}' 적용")

    db.commit()

    op_ko = _OP_KO.get(gimmick.operator or "", "")
    summary_header = f"■ 기믹: {gimmick.name}"
    if gimmick.action_type == "kill_if_stat":
        summary_header += f"\n조건: {gimmick.stat} {op_ko} {gimmick.threshold}"

    return {
        "gimmick_name": gimmick.name,
        "action_type":  gimmick.action_type,
        "affected":     affected,
        "log_lines":    log_lines,
        "summary":      summary_header + "\n\n" + "\n".join(log_lines),
    }
