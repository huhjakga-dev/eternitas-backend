import random
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .models import WorkSession, PrecursorLog, WorkLog, WorkSessionCrew
from src.runners.models import Crew, Cargo, CargoPattern, Equipment, CrewEquipment
from src.common.schema import WorkStatus, PrecursorResult, DamageType
from src.common.utils import compute_max_caps, roll_vs_cargo


class WorkService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 전조 선언 ─────────────────────────────────────────────────────────────

    def handle_precursor_declaration(
        self,
        session: WorkSession,
        pattern_id: _uuid.UUID,
        crew_id: _uuid.UUID,
        stat: str,
        player_success: bool,
    ) -> dict:
        """
        전조 선언 처리: 화물/승무원 대항 판정 → 결과 결정 → 효과 누적 적용.
        둘 다 성공 → SUCCESS(버프), 둘 다 실패 → FAIL(디버프, 5% 대실패), 엇갈림 → INVALID.
        """
        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {"error": "패턴 없음"}

        crew = self.db.query(Crew).filter(Crew.id == crew_id).first()
        if not crew:
            return {"error": "승무원 없음"}

        cargo = self.db.query(Cargo).filter(Cargo.id == pattern.cargo_id).first()
        if not cargo:
            return {"error": "cargo 스탯을 찾을 수 없음"}

        cargo_stat_raw = getattr(cargo, stat, None)
        if cargo_stat_raw is None:
            return {"error": f"cargo 스탯을 찾을 수 없음: {stat}"}

        crew_stat_val  = int(getattr(crew, stat, 1) or 1)
        cargo_stat_val = int(cargo_stat_raw)

        equipment_penalty = self._apply_default_equipment_penalty(session)
        roll              = roll_vs_cargo(crew_stat_val, cargo_stat_val)
        auto_success      = roll["success"]

        if player_success and auto_success:
            result = PrecursorResult.SUCCESS
        elif not player_success and not auto_success:
            result = PrecursorResult.CRITICAL_FAIL if random.random() < 0.05 else PrecursorResult.FAIL
        else:
            result = PrecursorResult.INVALID

        applied_effect = self._calc_modifiers(result, pattern)
        merged = dict(session.precursor_effect or {})
        for k, v in applied_effect.items():
            merged[k] = round(merged.get(k, 0.0) + v, 6)
        session.precursor_effect = merged
        flag_modified(session, "precursor_effect")

        self.db.add(PrecursorLog(session_id=session.id, pattern_id=pattern.id, crew_id=crew_id, result=result))

        kill_detail = None
        if result == PrecursorResult.CRITICAL_FAIL and pattern.instant_kill:
            kill_detail = self._handle_critical_fail(session)
        else:
            session.status = WorkStatus.MAIN_WORK_READY

        self.db.commit()
        return {
            "result": result,
            "roll_detail": roll,
            "applied_effect": applied_effect,
            "kill_detail": kill_detail,
            "equipment_penalty": equipment_penalty,
        }

    # ── 본 작업 ──────────────────────────────────────────────────────────────

    def handle_main_work_execution(
        self, session: WorkSession, crew_id: _uuid.UUID, commands: list[dict]
    ) -> dict:
        """
        본 작업 처리 (참여자 1인분 제출).

        판정: roll_vs_cargo(스탯+버프, 화물 고정값).
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

        if cargo and cargo.total_turns:
            submitted = sum(cmd["count"] for cmd in commands)
            if submitted != cargo.total_turns:
                return {"error": f"명령 횟수 합계({submitted})가 화물 총 턴수({cargo.total_turns})와 일치하지 않음"}

        crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()
        ]
        all_participants: list[Crew] = (
            self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else [crew]
        )

        mods: dict             = session.precursor_effect or {}
        damage_modifier: float = mods.get("_damage_modifier", 0.0)
        damage_per_crew        = {p.crew_name: 0 for p in all_participants}
        summary: list[str]     = []
        interrupted            = False

        for cmd in commands:
            if interrupted:
                break
            line, interrupted = self._execute_command(
                session.id, cmd, crew, cargo, all_participants,
                mods, damage_per_crew, damage_multiplier, damage_modifier, damage_type,
            )
            summary.append(line)

        self.db.commit()

        if not any(not p.is_dead for p in all_participants):
            session.status       = WorkStatus.RESOLVED
            session.final_result = "fail"
            if cargo:
                cargo.failure_count = (cargo.failure_count or 0) + 1
            self.db.commit()
            return {
                "summary": summary, "interrupted": True,
                "damage_per_crew": damage_per_crew,
                "session_status": session.status, "session_result": "전멸 — 작업 실패",
            }

        session_result = self._finalize_if_all_done(session, cargo, all_participants)
        return {
            "summary": summary, "interrupted": interrupted,
            "damage_per_crew": damage_per_crew,
            "session_status": session.status, "session_result": session_result,
        }

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _execute_command(
        self,
        session_id: _uuid.UUID,
        cmd: dict,
        crew: Crew,
        cargo: Optional[Cargo],
        all_participants: list[Crew],
        mods: dict,
        damage_per_crew: dict[str, int],
        damage_multiplier: float,
        damage_modifier: float,
        damage_type: DamageType,
    ) -> tuple[str, bool]:
        """단일 커맨드 블록(stat × count) 처리. (summary_line, interrupted) 반환."""
        stat_buff      = float(mods.get(cmd["stat"], 0.0))
        effective_stat = max(1, (getattr(crew, cmd["stat"], 1) or 1) + stat_buff)
        cargo_fixed    = int(getattr(cargo, cmd["stat"], 15) or 15) if cargo else 15

        logs, ok, dmg, actual = [], 0, 0, 0
        interrupted = False

        for i in range(1, cmd["count"] + 1):
            actual += 1
            roll   = roll_vs_cargo(int(effective_stat), cargo_fixed)
            c_roll = roll["crew_roll"]

            if roll["success"]:
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
                    damage_per_crew[p.crew_name] = damage_per_crew.get(p.crew_name, 0) + shared
                    if self._apply_damage(p, shared, damage_type):
                        dead_names.append(p.crew_name)
                if dead_names:
                    logs.append(f"사망: {', '.join(dead_names)}")

                if not any(not p.is_dead for p in all_participants):
                    interrupted = True
                    break

        self.db.add(WorkLog(
            session_id=session_id, crew_id=crew.id,
            stat_type=cmd["stat"], planned_count=cmd["count"],
            actual_count=actual, success_count=ok,
            damage_taken=dmg, damage_type=damage_type, is_interrupted=interrupted,
        ))
        return f"[{cmd['stat'].upper()}] " + " / ".join(logs), interrupted

    def _apply_default_equipment_penalty(self, session: WorkSession) -> list[dict]:
        """기본 장비(is_default=True)를 모두 착용하지 않은 참여 승무원의 SP를 즉시 반감."""
        default_equips = self.db.query(Equipment).filter(Equipment.is_default == True).all()
        if not default_equips:
            return []

        default_ids = {e.id for e in default_equips}
        crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()
        ]
        participants = self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []

        penalized = []
        for p in participants:
            if p.is_dead:
                continue
            equipped_ids = {
                ce.equipment_id for ce in
                self.db.query(CrewEquipment).filter(
                    CrewEquipment.crew_id == p.id,
                    CrewEquipment.is_equipped == True,
                ).all()
            }
            missing = [e.name for e in default_equips if e.id not in equipped_ids]
            if missing:
                p.sp = max(0, (p.sp or 0) // 2)
                penalized.append({"crew": p.crew_name, "missing": missing, "sp_after": p.sp})

        return penalized

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
                return None

        logs          = self.db.query(WorkLog).filter(WorkLog.session_id == session.id).all()
        total_turns   = sum(l.planned_count for l in logs)
        total_success = sum(l.success_count for l in logs)
        final_success = total_turns > 0 and total_success > total_turns / 2

        session.status       = WorkStatus.RESOLVED
        session.final_result = "success" if final_success else "fail"
        if cargo:
            if final_success:
                cargo.success_count    = (cargo.success_count or 0) + 1
                cargo.observation_rate = min(100.0, (cargo.observation_rate or 0.0) + 10.0)
            else:
                cargo.failure_count = (cargo.failure_count or 0) + 1
        self.db.commit()
        return "최종 성공" if final_success else "최종 실패"

    def _handle_critical_fail(self, session: WorkSession) -> str:
        """대실패 즉사 처리 (instant_kill=True 보장된 호출). 커밋은 호출자가 수행."""
        crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew).filter(WorkSessionCrew.session_id == session.id).all()
        ]
        living = (
            [c for c in self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if not c.is_dead]
            if crew_ids else []
        )

        if not living:
            session.status = WorkStatus.MAIN_WORK_READY
            return "대실패 — 생존 승무원 없음"

        victim    = random.choice(living)
        self._kill(victim)
        remaining = [c for c in living if c.id != victim.id]

        if not remaining:
            session.status       = WorkStatus.RESOLVED
            session.final_result = "fail"
            return f"대실패 즉사 — {victim.crew_name} 사망, 생존자 없음 → 작업 종료"

        session.status = WorkStatus.MAIN_WORK_READY
        return f"대실패 즉사 — {victim.crew_name} 사망, 생존자 {len(remaining)}명"

    def _calc_modifiers(self, result: PrecursorResult, pattern: CargoPattern) -> dict:
        """전조 결과에 따른 보정 delta 반환."""
        if result == PrecursorResult.INVALID:
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
        if stat in ("health", "mentality"):
            max_hp, max_sp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv or 0, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp = max_hp
            crew.max_sp = max_sp
        if random.random() < 0.02:
            self._kill(crew)
            return True
        crew.sp = 0
        return False

    def _kill(self, crew: Crew) -> None:
        crew.hp         = 0
        crew.is_dead    = True
        crew.death_time = datetime.now(timezone.utc)
