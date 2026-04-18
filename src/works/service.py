import random
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from .models import WorkSession, PrecursorLog, WorkLog, WorkSessionCrew
from src.runners.models import Crew, CargoPattern
from src.common.schema import WorkStatus, PrecursorResult


class WorkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def handle_precursor_declaration(self, session: WorkSession) -> dict:
        """
        전조 선언 처리. 화물 패턴 조회 → PrecursorLog 생성 → PRECURSOR_ACTIVE.

        Args:
            session: WAITING_PRECURSOR 상태의 WorkSession

        Returns:
            {"pattern": str | None, "description": str | None}
        """
        pattern = (
            self.db.query(CargoPattern)
            .filter(CargoPattern.cargo_id == session.cargo_id)
            .first()
        )
        log = PrecursorLog(
            session_id=session.id,
            pattern_id=pattern.id if pattern else None,
        )
        self.db.add(log)
        session.status = WorkStatus.PRECURSOR_ACTIVE
        self.db.commit()
        return {
            "pattern": pattern.pattern_name if pattern else None,
            "description": pattern.description if pattern else None,
        }

    def handle_crew_response(
        self,
        session: WorkSession,
        crew_id: _uuid.UUID,
        result: PrecursorResult,
    ) -> dict:
        """
        승무원 대응 처리. 운영자 판정 결과 수신 → 버프/디버프 저장 → MAIN_WORK_READY.
        critical_fail이면 해당 승무원 즉시 사망.

        Args:
            session: PRECURSOR_ACTIVE 상태의 WorkSession
            crew_id: 대응한 승무원 ID
            result:  success / invalid / fail / critical_fail

        Returns:
            {"result": str, "message": str, "precursor_effect": dict}
        """
        log = (
            self.db.query(PrecursorLog)
            .filter(PrecursorLog.session_id == session.id, PrecursorLog.result == None)
            .first()
        )
        if not log:
            return {"error": "처리할 PrecursorLog 없음"}

        log.result  = result
        log.crew_id = crew_id
        session.precursor_effect = self._calc_modifiers(result, log.pattern_id)
        session.status = WorkStatus.MAIN_WORK_READY
        self.db.commit()

        if result == PrecursorResult.CRITICAL_FAIL:
            crew = self.db.query(Crew).filter(Crew.id == crew_id).first()
            if crew:
                self._kill(crew)
            msg = "대실패 — 승무원 사망"
        elif result == PrecursorResult.SUCCESS:
            msg = "성공 — 버프 적용"
        elif result == PrecursorResult.INVALID:
            msg = "무효 — 보정 없음"
        else:
            msg = "실패 — 디버프 적용"

        return {"result": result, "message": msg, "precursor_effect": session.precursor_effect}

    def handle_main_work_execution(
        self,
        session: WorkSession,
        crew_id: _uuid.UUID,
        commands: list[dict],
    ) -> dict:
        """
        본 작업 처리. 운영자가 파싱된 명령 목록을 직접 전달.
        스탯별 1d20 + 스탯값 + 버프/디버프 vs 화물 1d20 + 15 턴 판정.
        실패 시 데미지를 참여 승무원 전체에 분산. 사망 시 중단 → RESOLVED.

        Args:
            session:  MAIN_WORK_READY 상태의 WorkSession
            crew_id:  작업 명령을 내린 승무원 ID
            commands: [{"stat": str, "count": int}, ...]

        Returns:
            {"summary": list[str], "interrupted": bool, "session_status": str}
        """
        crew = self.db.query(Crew).filter(Crew.id == crew_id).first()
        if not crew:
            return {"error": f"승무원 {crew_id} 없음"}

        crew_ids = [sc.crew_id for sc in self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()]
        participants: list[Crew] = self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else [crew]
        n = max(len(participants), 1)

        mods: dict = session.precursor_effect or {}
        summary: list[str] = []
        interrupted = False

        for cmd in commands:
            if interrupted:
                break
            logs, ok, dmg, actual = [], 0, 0, 0

            for i in range(1, cmd["count"] + 1):
                actual += 1
                stat_val: int   = getattr(crew, cmd["stat"], 0) or 0
                buff: float     = mods.get(cmd["stat"], 0)
                c_roll = random.randint(1, 20) + stat_val + buff
                g_roll = random.randint(1, 20) + 15

                if c_roll >= g_roll:
                    ok += 1
                    logs.append(f"第{i}턴: 성공 ({c_roll} vs {g_roll})")
                else:
                    raw = max(1, int((g_roll - c_roll) * 2
                                    * (1 - mods.get("_damage_reduction", 0.0))
                                    * (1 + mods.get("_damage_increase", 0.0))))
                    shared = max(1, raw // n)
                    dmg += shared
                    note = f" (전체 {raw} → {n}명 분산)" if n > 1 else ""
                    logs.append(f"第{i}턴: 실패 ({c_roll} vs {g_roll}) → HP -{shared}{note}")

                    dead = []
                    for p in participants:
                        p.hp = max(0, (p.hp or 0) - shared)
                        if p.hp <= 0:
                            self._kill(p)
                            dead.append(p.crew_name)
                    if dead:
                        logs.append(f"사망: {', '.join(dead)}")
                        interrupted = True
                        break

            self.db.add(WorkLog(
                session_id=session.id, crew_id=crew.id,
                stat_type=cmd["stat"], planned_count=cmd["count"],
                actual_count=actual, success_count=ok,
                damage_taken=dmg, is_interrupted=interrupted,
            ))
            summary.append(f"[{cmd['stat'].upper()}] " + " / ".join(logs))

        if interrupted:
            session.status = WorkStatus.RESOLVED
        self.db.commit()

        return {"summary": summary, "interrupted": interrupted, "session_status": session.status}

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _calc_modifiers(self, result: PrecursorResult, pattern_id: Optional[_uuid.UUID]) -> dict:
        """
        전조 결과에 따라 본 작업 보정치 dict 반환.
        success → buff, 그 외 fail/critical_fail → debuff, invalid → 빈 dict.
        """
        if result == PrecursorResult.INVALID or pattern_id is None:
            return {}

        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {}

        if result == PrecursorResult.SUCCESS:
            mods = dict(pattern.buff_stat_json or {})
            mods["_damage_reduction"] = pattern.buff_damage_reduction or 0.0
        else:
            mods = dict(pattern.debuff_stat_json or {})
            mods["_damage_increase"] = pattern.debuff_demage_increase or 0.0
        return mods

    def _kill(self, crew: Crew) -> None:
        """승무원 사망 처리. 1시간 후 스케줄러가 자동 부활."""
        crew.hp = 0
        crew.is_dead = True
        crew.death_time = datetime.now(timezone.utc)
