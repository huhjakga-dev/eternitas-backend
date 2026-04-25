"""
공통 화물 서비스 베이스 클래스.
체력 차감, 즉사, 정신 붕괴, 상태이상 적용, 세션 강제 종료 등 재사용 가능한 메커니즘을 모아둔다.
"""
import random
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.runners.models import (
    Crew, Cargo, CargoPattern, StatusEffect, CrewStatusEffect
)
from src.works.models import WorkSession, WorkSessionCrew
from src.common.schema import WorkStatus
from src.common.utils import compute_max_caps, roll_vs_cargo


class BaseCargoService:
    def __init__(self, db: Session, session: WorkSession, cargo: Cargo):
        self.db      = db
        self.session = session
        self.cargo   = cargo

    # ── 판정 ──────────────────────────────────────────────────────────────────

    def roll_stat(self, crew: Crew, stat: str) -> dict:
        """승무원 스탯 vs 화물 동일 스탯 대항 판정."""
        crew_val  = int(getattr(crew, stat, 1) or 1)
        cargo_val = int(getattr(self.cargo, stat, 10) or 10)
        return roll_vs_cargo(crew_val, cargo_val)

    # ── 데미지 / 사망 ─────────────────────────────────────────────────────────

    def kill(self, crew: Crew) -> str:
        crew.hp         = 0
        crew.is_dead    = True
        crew.death_time = datetime.now(timezone.utc)
        return f"{crew.crew_name} 즉사"

    def hp_damage(self, crew: Crew, amount: int) -> str:
        crew.hp = max(0, (crew.hp or 0) - amount)
        if crew.hp <= 0 and not crew.is_dead:
            return self.kill(crew)
        return f"{crew.crew_name} HP -{amount} → 잔여 {crew.hp}"

    def sp_damage(self, crew: Crew, amount: int) -> str:
        before  = crew.sp or 0
        crew.sp = max(0, before - amount)
        msg     = f"{crew.crew_name} SP -{amount} → 잔여 {crew.sp}"
        if crew.sp <= 0 and before > 0:
            collapse = self._mental_collapse(crew)
            msg += f"\n  {collapse}"
        return msg

    def _mental_collapse(self, crew: Crew) -> str:
        stat = random.choice(["health", "mentality", "strength", "inteligence", "luckiness"])
        setattr(crew, stat, max(1, (getattr(crew, stat) or 1) - 1))
        if stat in ("health", "mentality"):
            mhp, msp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv or 0, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp, crew.max_sp = mhp, msp
        if random.random() < 0.02:
            self.kill(crew)
            return "정신 붕괴 즉사"
        crew.sp = 0
        return f"정신 붕괴 ({stat} -1)"

    # ── 상태이상 ──────────────────────────────────────────────────────────────

    def apply_se(self, crew: Crew, se_name: str) -> str:
        """이름으로 이 화물에 연결된 상태이상을 승무원에게 적용. stat_json 즉시 반영."""
        se = self.db.query(StatusEffect).filter(
            StatusEffect.name     == se_name,
            StatusEffect.cargo_id == self.cargo.id,
        ).first()
        if not se:
            return f"[{se_name}] 상태이상이 이 화물에 등록되어 있지 않습니다"
        already = self.db.query(CrewStatusEffect).filter(
            CrewStatusEffect.crew_id          == crew.id,
            CrewStatusEffect.status_effect_id == se.id,
        ).first()
        if already:
            return f"{crew.crew_name} — [{se_name}] 이미 적용 중"
        expires = (
            datetime.now(timezone.utc) + timedelta(minutes=se.duration_minutes)
        ) if se.duration_minutes else None
        self.db.add(CrewStatusEffect(
            crew_id=crew.id, status_effect_id=se.id,
            expires_at=expires, tick_count=0,
        ))
        stat_msgs = self._apply_stat_json(crew, se.stat_json)
        msg = f"{crew.crew_name} → [{se_name}] 부여"
        if stat_msgs:
            msg += "  (" + ", ".join(stat_msgs) + ")"
        return msg

    def _apply_stat_json(self, crew: Crew, stat_json: dict | None) -> list[str]:
        if not stat_json:
            return []
        msgs = []
        for stat, delta in stat_json.items():
            current = getattr(crew, stat, None)
            if current is None:
                continue
            setattr(crew, stat, max(1, (current or 1) + delta))
            msgs.append(f"{stat} {'+' if delta > 0 else ''}{delta}")
        if any(s in (stat_json or {}) for s in ("health", "mentality")):
            mhp, msp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv or 0, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp, crew.max_sp = mhp, msp
        return msgs

    # ── 세션 제어 ─────────────────────────────────────────────────────────────

    def force_success(self) -> None:
        self.session.status       = WorkStatus.RESOLVED
        self.session.final_result = "success"
        self.cargo.success_count    = (self.cargo.success_count    or 0) + 1
        self.cargo.observation_rate = min(100.0, (self.cargo.observation_rate or 0.0) + 10.0)

    def force_fail(self) -> None:
        self.session.status       = WorkStatus.RESOLVED
        self.session.final_result = "fail"
        self.cargo.failure_count = (self.cargo.failure_count or 0) + 1

    # ── 조회 헬퍼 ─────────────────────────────────────────────────────────────

    def get_session_crews(self) -> list[Crew]:
        ids = [sc.crew_id for sc in self.db.query(WorkSessionCrew).filter(
            WorkSessionCrew.session_id == self.session.id
        ).all()]
        return self.db.query(Crew).filter(Crew.id.in_(ids)).all() if ids else []

    def get_alive_crews(self) -> list[Crew]:
        return [c for c in self.get_session_crews() if not c.is_dead]

    def get_pattern_by_name(self, name: str) -> CargoPattern | None:
        return self.db.query(CargoPattern).filter(
            CargoPattern.cargo_id     == self.cargo.id,
            CargoPattern.pattern_name == name,
        ).first()

    def apply_precursor_effect(self, mods: dict) -> None:
        """전조 효과(버프/디버프)를 세션에 누적 적용."""
        merged = dict(self.session.precursor_effect or {})
        for k, v in mods.items():
            merged[k] = round(merged.get(k, 0.0) + v, 6)
        self.session.precursor_effect = merged
        flag_modified(self.session, "precursor_effect")

    # ── 서브클래스 구현 ───────────────────────────────────────────────────────

    def run_precursor(self, pattern_id: uuid.UUID, result: str, crew: Crew) -> dict:
        """
        result: "success" | "fail" | "critical_fail"
        반환: {"log": [str, ...], "resolved": bool, "final_result": str|None, ...}
        """
        raise NotImplementedError


class GenericCargoService(BaseCargoService):
    """
    DB에 등록된 CargoPattern 버프/디버프를 그대로 적용하는 범용 서비스.
    cargo-specific 서비스가 없는 화물에 자동으로 사용됨.
    """

    def run_precursor(self, pattern_id: uuid.UUID, result: str, crew: Crew) -> dict:
        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {"log": ["패턴을 찾을 수 없습니다."], "resolved": False}

        log = [f"■ 전조: {pattern.pattern_name}", f"결과: {result}", ""]

        if result == "success":
            mods = dict(pattern.buff_stat_json or {})
            if pattern.buff_damage_reduction:
                mods["_damage_modifier"] = -(pattern.buff_damage_reduction)
            if mods:
                self.apply_precursor_effect(mods)
                log.append("버프 적용: " + ", ".join(f"{k} +{v}" for k, v in mods.items() if k != "_damage_modifier"))

        elif result in ("fail", "critical_fail"):
            is_cf = result == "critical_fail" or (result == "fail" and random.random() < 0.05)
            if is_cf and pattern.instant_kill:
                msg = self.kill(crew)
                log.append(f"대실패 즉사 — {msg}")
                alive = self.get_alive_crews()
                if not alive:
                    self.force_fail()
                    log.append("전원 사망 — 작업 실패 처리.")
                return {"log": log, "resolved": not bool(alive)}

            mods = dict(pattern.debuff_stat_json or {})
            if pattern.debuff_demage_increase:
                mods["_damage_modifier"] = pattern.debuff_demage_increase
            if mods:
                self.apply_precursor_effect(mods)
                log.append("디버프 적용: " + ", ".join(f"{k} {v:+}" for k, v in mods.items() if k != "_damage_modifier"))

        self.session.status = WorkStatus.MAIN_WORK_READY
        log.append(f"\n세션 상태: {self.session.status}")
        return {"log": log, "resolved": False}
