import random
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .models import WorkSession, PrecursorLog, WorkLog, WorkSessionCrew
from src.runners.models import Crew, Cargo, CargoPattern
from src.common.schema import WorkStatus, PrecursorResult, DamageType


class WorkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 전조 선언 ─────────────────────────────────────────────────────────────

    def handle_precursor_declaration(self, session: WorkSession) -> dict:
        """
        전조 선언 처리. 화물 패턴 조회 → PrecursorLog 생성 → PRECURSOR_ACTIVE.
        여러 번 호출해도 PrecursorLog가 1:N으로 쌓이므로 2회 전조 지원.
        """
        pattern = (
            self.db.query(CargoPattern)
            .filter(CargoPattern.cargo_id == session.cargo_id)
            .first()
        )
        self.db.add(PrecursorLog(session_id=session.id, pattern_id=pattern.id if pattern else None))
        session.status = WorkStatus.PRECURSOR_ACTIVE
        self.db.commit()
        return {
            "pattern": pattern.pattern_name if pattern else None,
            "description": pattern.description if pattern else None,
        }

    # ── 승무원 대응 ───────────────────────────────────────────────────────────

    def handle_crew_response(
        self, session: WorkSession, crew_id: _uuid.UUID, result: PrecursorResult
    ) -> dict:
        """
        승무원 대응 처리. 전조 효과를 precursor_effect에 누적 → MAIN_WORK_READY.
        여러 번 호출 시 효과가 합산됨 (스탯 보정 합산, 데미지 배율 증감 합산).
        critical_fail + instant_kill=True → 참여자 랜덤 1명 즉사.
        """
        log = (
            self.db.query(PrecursorLog)
            .filter(PrecursorLog.session_id == session.id, PrecursorLog.result == None)
            .first()
        )
        if not log:
            return {"error": "처리할 PrecursorLog 없음"}

        log.result = result
        log.crew_id = crew_id

        new_mods = self._calc_modifiers(result, log.pattern_id)
        merged = dict(session.precursor_effect or {})
        for k, v in new_mods.items():
            merged[k] = round(merged.get(k, 0.0) + v, 6)
        session.precursor_effect = merged
        flag_modified(session, "precursor_effect")

        if result == PrecursorResult.CRITICAL_FAIL:
            msg = self._handle_critical_fail(session, log.pattern_id)
        else:
            session.status = WorkStatus.MAIN_WORK_READY
            self.db.commit()
            msg = {
                PrecursorResult.SUCCESS: "성공 — 버프 적용",
                PrecursorResult.INVALID: "무효 — 보정 없음",
                PrecursorResult.FAIL:    "실패 — 디버프 적용",
            }[result]

        return {"result": result, "message": msg, "precursor_effect": session.precursor_effect}

    # ── 본 작업 ──────────────────────────────────────────────────────────────

    def handle_main_work_execution(
        self, session: WorkSession, crew_id: _uuid.UUID, commands: list[dict]
    ) -> dict:
        """
        본 작업 처리 (참여자 1인분 제출).

        판정: 1d(스탯×5 + 버프×5) vs 화물 고정 스탯값.
        데미지: round((차이) × damage_multiplier × (1 + _damage_modifier)), 생존자 균등 분산.
        사망 판정:
          - HP/BOTH 타입: HP=0 → 즉사
          - SP/BOTH 타입: SP=0 → 정신 붕괴 (랜덤 스탯 -1, 2% 즉사)
        전원 사망 → RESOLVED(전멸).
        모든 참여자 제출 or 사망 시 → 과반수 성공 여부 판정 → RESOLVED.
        """
        if session.status == WorkStatus.RESOLVED:
            return {"error": "이미 종료된 세션"}

        crew = self.db.query(Crew).filter(Crew.id == crew_id).first()
        if not crew:
            return {"error": f"승무원 {crew_id} 없음"}
        if crew.is_dead:
            return {"error": "사망 상태의 승무원은 작업 불가"}

        cargo             = self.db.query(Cargo).filter(Cargo.id == session.cargo_id).first()
        damage_type       = cargo.damage_type if cargo else DamageType.HP
        damage_multiplier = float(cargo.damage_multiplier) if cargo else 0.1

        crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()
        ]
        all_participants: list[Crew] = (
            self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else [crew]
        )

        mods: dict             = session.precursor_effect or {}
        damage_modifier: float = mods.get("_damage_modifier", 0.0)

        summary:     list[str] = []
        interrupted            = False

        for cmd in commands:
            if interrupted:
                break

            stat_buff: float = mods.get(cmd["stat"], 0.0)
            effective_stat   = max(1, (getattr(crew, cmd["stat"], 1) or 1) + stat_buff)
            dice_max: int    = max(1, round(effective_stat * 5))
            cargo_fixed: int = int(getattr(cargo, cmd["stat"], 15) or 15) if cargo else 15

            logs, ok, dmg, actual = [], 0, 0, 0

            for i in range(1, cmd["count"] + 1):
                if interrupted:
                    break
                actual += 1
                c_roll = random.randint(1, dice_max)

                if c_roll > cargo_fixed:
                    ok += 1
                    logs.append(f"제{i}턴: 성공 ({c_roll} vs {cargo_fixed})")
                else:
                    alive  = [p for p in all_participants if not p.is_dead]
                    n      = max(len(alive), 1)
                    raw    = max(1, round((cargo_fixed - c_roll) * damage_multiplier * (1 + damage_modifier)))
                    shared = max(1, raw // n)
                    note   = f" (전체 {raw} → {n}명 분산)" if n > 1 else ""
                    logs.append(f"제{i}턴: 실패 ({c_roll} vs {cargo_fixed}) → -{shared}{note}")
                    dmg += shared

                    dead_names = []
                    for p in alive:
                        if self._apply_damage(p, shared, damage_type):
                            dead_names.append(p.crew_name)
                    if dead_names:
                        logs.append(f"사망: {', '.join(dead_names)}")

                    if not any(not p.is_dead for p in all_participants):
                        interrupted = True
                        break

            self.db.add(WorkLog(
                session_id=session.id, crew_id=crew.id,
                stat_type=cmd["stat"], planned_count=cmd["count"],
                actual_count=actual, success_count=ok,
                damage_taken=dmg, damage_type=damage_type, is_interrupted=interrupted,
            ))
            summary.append(f"[{cmd['stat'].upper()}] " + " / ".join(logs))

        self.db.commit()

        # 전멸 체크
        if not any(not p.is_dead for p in all_participants):
            session.status = WorkStatus.RESOLVED
            if cargo:
                cargo.failure_count = (cargo.failure_count or 0) + 1
            self.db.commit()
            return {
                "summary": summary, "interrupted": True,
                "session_status": session.status, "session_result": "전멸 — 작업 실패",
            }

        # 모든 참여자 완료 시 최종 판정
        session_result = self._finalize_if_all_done(session, cargo, all_participants)
        return {
            "summary": summary, "interrupted": interrupted,
            "session_status": session.status, "session_result": session_result,
        }

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _finalize_if_all_done(
        self,
        session: WorkSession,
        cargo: Optional[Cargo],
        all_participants: list[Crew],
    ) -> Optional[str]:
        """모든 참여자가 제출 완료 or 사망이면 과반수 성공 판정 → RESOLVED."""
        submitted_ids = {
            wl.crew_id
            for wl in self.db.query(WorkLog).filter(WorkLog.session_id == session.id).all()
        }
        for p in all_participants:
            if p.id not in submitted_ids and not p.is_dead:
                return None  # 아직 미제출 생존자 있음

        logs          = self.db.query(WorkLog).filter(WorkLog.session_id == session.id).all()
        total_turns   = sum(l.planned_count for l in logs)
        total_success = sum(l.success_count for l in logs)
        final_success = total_turns > 0 and total_success > total_turns / 2

        session.status = WorkStatus.RESOLVED
        if cargo:
            if final_success:
                cargo.success_count    = (cargo.success_count or 0) + 1
                cargo.observation_rate = min(100.0, (cargo.observation_rate or 0.0) + 10.0)
            else:
                cargo.failure_count = (cargo.failure_count or 0) + 1
        self.db.commit()
        return "최종 성공" if final_success else "최종 실패"

    def _handle_critical_fail(self, session: WorkSession, pattern_id: Optional[_uuid.UUID]) -> str:
        """대실패 처리. instant_kill=True일 때만 참여자 랜덤 1명 즉사."""
        pattern = (
            self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
            if pattern_id else None
        )
        if not (pattern and pattern.instant_kill):
            session.status = WorkStatus.MAIN_WORK_READY
            self.db.commit()
            return "대실패 — 즉사 기믹 없음"

        crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()
        ]
        living = [
            c for c in self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if not c.is_dead
        ] if crew_ids else []

        if not living:
            session.status = WorkStatus.MAIN_WORK_READY
            self.db.commit()
            return "대실패 — 생존 승무원 없음"

        victim    = random.choice(living)
        self._kill(victim)
        remaining = [c for c in living if c.id != victim.id]

        if not remaining:
            session.status = WorkStatus.RESOLVED
            self.db.commit()
            return f"대실패 즉사 — {victim.crew_name} 사망, 생존자 없음 → 작업 종료"

        session.status = WorkStatus.MAIN_WORK_READY
        self.db.commit()
        return f"대실패 즉사 — {victim.crew_name} 사망, 생존자 {len(remaining)}명"

    def _calc_modifiers(self, result: PrecursorResult, pattern_id: Optional[_uuid.UUID]) -> dict:
        """
        전조 결과에 따른 보정 delta 반환 (누적 합산용).
        _damage_modifier: 양수 = 데미지 증가, 음수 = 데미지 감소.
        """
        if result == PrecursorResult.INVALID or pattern_id is None:
            return {}

        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {}

        if result == PrecursorResult.SUCCESS:
            mods = dict(pattern.buff_stat_json or {})
            if pattern.buff_damage_reduction:
                mods["_damage_modifier"] = -(pattern.buff_damage_reduction)
        else:  # FAIL or CRITICAL_FAIL
            mods = dict(pattern.debuff_stat_json or {})
            if pattern.debuff_demage_increase:
                mods["_damage_modifier"] = pattern.debuff_demage_increase
        return mods

    def _apply_damage(self, crew: Crew, amount: int, damage_type: DamageType) -> bool:
        """데미지 적용. 사망/붕괴 시 True 반환."""
        if damage_type == DamageType.BOTH:
            hp_dmg, sp_dmg = amount // 2, amount - amount // 2
        elif damage_type == DamageType.HP:
            hp_dmg, sp_dmg = amount, 0
        else:  # SP
            hp_dmg, sp_dmg = 0, amount

        if hp_dmg:
            crew.hp = max(0, (crew.hp or 0) - hp_dmg)
            if crew.hp <= 0 and not crew.is_dead:
                self._kill(crew)
                return True

        if sp_dmg and not crew.is_dead:
            crew.sp = max(0, (crew.sp or 0) - sp_dmg)
            if crew.sp <= 0:
                return self._mental_collapse(crew)

        return False

    def _mental_collapse(self, crew: Crew) -> bool:
        """정신 붕괴. 랜덤 스탯 영구 -1, 2% 확률 즉사. 즉사 시 True 반환."""
        stat = random.choice(["health", "mentality", "strength", "inteligence", "luckiness"])
        setattr(crew, stat, max(1, (getattr(crew, stat) or 1) - 1))
        if random.random() < 0.02:
            self._kill(crew)
            return True
        crew.sp = 0
        return False

    def _kill(self, crew: Crew) -> None:
        """승무원 사망 처리. 1시간 후 스케줄러가 자동 부활."""
        crew.hp = 0
        crew.is_dead = True
        crew.death_time = datetime.now(timezone.utc)
