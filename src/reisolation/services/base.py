"""
재격리 공통 서비스 베이스 클래스.
"""
import random
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from src.runners.models import Crew, Cargo, StatusEffect, CrewStatusEffect
from src.reisolation.models import ReIsolationSession, ReIsolationSessionCrew, ReisolationPattern
from src.common.schema import ReIsolationStatus, DamageType
from src.common.utils import compute_max_caps, roll_vs_cargo


class BaseReisolationService:
    def __init__(self, db: Session, session: ReIsolationSession, cargo: Cargo):
        self.db      = db
        self.session = session
        self.cargo   = cargo

    # ── 판정 ──────────────────────────────────────────────────────────────────

    def roll_stat(self, crew: Crew, stat: str) -> dict:
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
        sp_before = crew.sp or 0
        crew.sp   = max(0, sp_before - amount)
        msg       = f"{crew.crew_name} SP -{amount} → 잔여 {crew.sp}"
        if crew.sp <= 0 and sp_before > 0:
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

    def apply_damage(self, crew: Crew, amount: int, damage_type: DamageType) -> str:
        if damage_type == DamageType.BOTH:
            hp_dmg, sp_dmg = amount // 2, amount - amount // 2
        elif damage_type == DamageType.HP:
            hp_dmg, sp_dmg = amount, 0
        else:
            hp_dmg, sp_dmg = 0, amount

        msgs = []
        if hp_dmg:
            msgs.append(self.hp_damage(crew, hp_dmg))
        if sp_dmg and not crew.is_dead:
            msgs.append(self.sp_damage(crew, sp_dmg))
        return " / ".join(msgs)

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

    def apply_se_by_id(self, crew: Crew, se_id: uuid.UUID) -> str:
        se = self.db.query(StatusEffect).filter(StatusEffect.id == se_id).first()
        if not se:
            return f"상태이상 없음 (id={se_id})"
        already = self.db.query(CrewStatusEffect).filter(
            CrewStatusEffect.crew_id          == crew.id,
            CrewStatusEffect.status_effect_id == se.id,
        ).first()
        if already:
            return f"{crew.crew_name} — [{se.name}] 이미 적용 중"
        expires = (
            datetime.now(timezone.utc) + timedelta(minutes=se.duration_minutes)
        ) if se.duration_minutes else None
        self.db.add(CrewStatusEffect(
            crew_id=crew.id, status_effect_id=se.id,
            expires_at=expires, tick_count=0,
        ))
        stat_msgs = self._apply_stat_json(crew, se.stat_json)
        msg = f"{crew.crew_name} → [{se.name}] 부여"
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
            from src.common.utils import compute_max_caps
            mhp, msp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv or 0, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp, crew.max_sp = mhp, msp
        return msgs

    # ── 세션 제어 ─────────────────────────────────────────────────────────────

    def force_resolve(self, success: bool = True) -> None:
        self.session.status = ReIsolationStatus.RESOLVED
        self.cargo.is_escaped = False
        se_ids = [
            row.id for row in
            self.db.query(StatusEffect).filter(StatusEffect.cargo_id == self.cargo.id).all()
        ]
        if se_ids:
            self.db.query(CrewStatusEffect).filter(
                CrewStatusEffect.status_effect_id.in_(se_ids)
            ).delete(synchronize_session=False)

    # ── 조회 헬퍼 ─────────────────────────────────────────────────────────────

    def get_session_crews(self) -> list[Crew]:
        ids = [sc.crew_id for sc in self.db.query(ReIsolationSessionCrew).filter(
            ReIsolationSessionCrew.session_id == self.session.id
        ).all()]
        return self.db.query(Crew).filter(Crew.id.in_(ids)).all() if ids else []

    def get_alive_crews(self) -> list[Crew]:
        return [c for c in self.get_session_crews() if not c.is_dead]

    def get_pattern_by_name(self, name: str) -> ReisolationPattern | None:
        return self.db.query(ReisolationPattern).filter(
            ReisolationPattern.cargo_id    == self.cargo.id,
            ReisolationPattern.pattern_name == name,
        ).first()

    # ── 서브클래스 구현 ───────────────────────────────────────────────────────

    def run_pattern(
        self,
        pattern_id: uuid.UUID,
        crew_ids: list[uuid.UUID],
        stat: str | None,
        response_success: bool | None,
    ) -> dict:
        """
        반환: {"log": [str, ...], "resolved": bool, ...}
        """
        raise NotImplementedError


class GenericReisolationService(BaseReisolationService):
    """
    DB에 등록된 ReisolationPattern 효과를 그대로 적용하는 범용 서비스.
    cargo-specific 서비스가 없는 화물에 자동으로 사용됨.
    """

    def run_pattern(
        self,
        pattern_id: uuid.UUID,
        crew_ids: list[uuid.UUID],
        stat: str | None,
        response_success: bool | None,
    ) -> dict:
        import random as _r

        pattern = self.db.query(ReisolationPattern).filter(ReisolationPattern.id == pattern_id).first()
        if not pattern:
            return {"log": ["패턴을 찾을 수 없습니다."], "resolved": False}

        target_crews = self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []
        log: list[str] = [f"■ 재격리 패턴: {pattern.pattern_name}", ""]

        # ── 크루별 판정 ───────────────────────────────────────────────────
        roll_details: dict[str, dict] = {}
        crew_results: dict[uuid.UUID, str | None] = {}

        for crew in target_crews:
            dice_result = None
            if stat:
                crew_stat  = max(1, int(getattr(crew, stat, 1) or 1))
                cargo_stat = int(getattr(self.cargo, stat, 15) or 15)
                dice_max   = max(1, crew_stat * 5)
                roll       = _r.randint(1, dice_max)
                roll_details[crew.crew_name] = {"roll": roll, "vs": cargo_stat, "dice": f"1d{dice_max}"}
                log.append(f"{crew.crew_name} 주사위: {roll} (1d{dice_max}) vs {cargo_stat}")

                if roll > cargo_stat:
                    dice_result = "success"
                elif _r.random() < (pattern.critical_fail_rate or 0.05):
                    dice_result = "critical_fail"
                else:
                    dice_result = "fail"

            if response_success is None:
                overall = dice_result
            elif not response_success:
                overall = "critical_fail" if dice_result == "critical_fail" else "fail"
            else:
                overall = dice_result if dice_result else "success"

            crew_results[crew.id] = overall
            if overall:
                log.append(f"  → {crew.crew_name}: {overall}")

        log.append("")

        # ── 효과 적용 ─────────────────────────────────────────────────────
        effects_log: list[str] = []
        resolve_triggered = False

        for effect in (pattern.unconditional_effects or []):
            if self._apply_effect(effect, target_crews, effects_log):
                resolve_triggered = True

        for crew in target_crews:
            result = crew_results.get(crew.id)
            effect_list = (
                pattern.on_success_effects       if result == "success"       else
                pattern.on_critical_fail_effects if result == "critical_fail" else
                pattern.on_fail_effects          if result == "fail"          else []
            ) or []
            for effect in effect_list:
                if self._apply_effect(effect, [crew], effects_log):
                    resolve_triggered = True

        log.extend(effects_log)

        if resolve_triggered and self.session.status == ReIsolationStatus.ACTIVE:
            self.force_resolve()
            log.append("\n→ 재격리 완료")

        return {
            "log":          log,
            "roll_details": roll_details,
            "crew_results": {c.crew_name: crew_results.get(c.id) for c in target_crews},
            "resolved":     resolve_triggered,
        }

    def _apply_effect(self, effect: dict, targets: list[Crew], log: list[str]) -> bool:
        etype = effect.get("type")
        tmode = effect.get("target", "random")
        alive = [c for c in targets if not c.is_dead]

        if not alive and etype != "resolve":
            return False

        selected = [random.choice(alive)] if tmode == "random" else alive

        if etype == "instant_kill":
            for crew in selected:
                log.append(self.kill(crew))

        elif etype == "status_effect":
            se_id = effect.get("status_effect_id")
            if se_id:
                for crew in selected:
                    log.append(self.apply_se_by_id(crew, uuid.UUID(se_id)))

        elif etype == "damage":
            amount    = int(effect.get("amount") or 0)
            dtype_str = effect.get("damage_type", "hp")
            dtype     = DamageType(dtype_str) if dtype_str in DamageType._value2member_map_ else DamageType.HP
            for crew in selected:
                log.append(self.apply_damage(crew, amount, dtype))

        elif etype == "resolve":
            log.append("상황 해결 — 재격리 완료")
            return True

        return False
