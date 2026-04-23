import random
import uuid as _uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from .models import ReIsolationSession, ReIsolationSessionCrew, ReIsolationLog, ReisolationPattern
from src.runners.models import Crew, Cargo, CrewStatusEffect, StatusEffect
from src.common.schema import ReIsolationStatus, DamageType
from src.common.utils import get_equipped_weapon

# ── 등급별 상수 ────────────────────────────────────────────────────────────────

GRADE_WEIGHT: dict[str, int] = {
    "standard":     5,
    "non_standard": 15,
    "overload":     30,
    "fixed":        50,
}

GRADE_HP: dict[str, int] = {
    "standard":     100,
    "non_standard": 230,
    "overload":     330,
    "fixed":        500,
}

GRADE_COUNTER: dict[str, tuple[int, int]] = {
    "standard":     (3, 6),
    "non_standard": (6, 8),
    "overload":     (8, 10),
    "fixed":        (12, 17),
}


def _grade_str(cargo: Cargo) -> str:
    return cargo.grade.value if hasattr(cargo.grade, "value") else str(cargo.grade)


def _roll_with_weapon(crew: Crew, weapon: dict) -> int:
    r = random.randint(1, max(1, (crew.luckiness or 1) * 5))
    if weapon["min_roll"] > 0:
        r = max(weapon["min_roll"], r)
    return r + weapon["hit_bonus"]


class ReIsolationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, cargo_id: _uuid.UUID, crew_ids: list[_uuid.UUID]) -> dict:
        cargo = self.db.query(Cargo).filter(Cargo.id == cargo_id).first()
        if not cargo:
            return {"error": "화물 없음"}
        if not cargo.is_escaped:
            return {"error": "탈출 상태가 아닌 화물입니다"}

        grade    = _grade_str(cargo)
        max_hp   = GRADE_HP.get(grade, 100)
        threshold = int((cargo.cause or 10) * 1.2) + GRADE_WEIGHT.get(grade, 5)

        session = ReIsolationSession(
            cargo_id=cargo_id,
            status=ReIsolationStatus.ACTIVE,
            cargo_current_hp=max_hp,
            cargo_max_hp=max_hp,
        )
        self.db.add(session)
        self.db.flush()

        for cid in crew_ids:
            self.db.add(ReIsolationSessionCrew(session_id=session.id, crew_id=cid))

        self.db.commit()
        return {
            "session_id":  str(session.id),
            "cargo_name":  cargo.cargo_name,
            "cargo_max_hp": max_hp,
            "threshold":   threshold,
            "status":      session.status,
        }

    def execute_attack(self, session: ReIsolationSession, crew_id: _uuid.UUID) -> dict:
        if session.status != ReIsolationStatus.ACTIVE:
            return {"error": "종료된 세션"}

        crew = self.db.query(Crew).filter(Crew.id == crew_id).first()
        if not crew:
            return {"error": "승무원 없음"}
        if crew.is_dead:
            return {"error": "사망 승무원은 공격 불가"}

        cargo         = self.db.query(Cargo).filter(Cargo.id == session.cargo_id).first()
        grade         = _grade_str(cargo)
        threshold     = int((cargo.cause or 10) * 1.2) + GRADE_WEIGHT.get(grade, 5)
        counter_range = GRADE_COUNTER.get(grade, (3, 6))
        damage_type   = cargo.damage_type if cargo else DamageType.HP
        weapon        = get_equipped_weapon(self.db, crew_id)

        # 공격 판정
        raw_roll   = random.randint(1, max(1, (crew.luckiness or 1) * 5))
        if weapon["min_roll"] > 0:
            raw_roll = max(weapon["min_roll"], raw_roll)
        final_roll = raw_roll + weapon["hit_bonus"]
        success    = final_roll >= threshold

        damage_dealt = 0
        if success:
            damage_dealt = random.randint(max(1, weapon["damage_min"]), max(1, weapon["damage_max"]))
            session.cargo_current_hp = max(0, session.cargo_current_hp - damage_dealt)

        # 화물 반격
        counter_dmg  = random.randint(*counter_range)
        participants = self._get_participants(session)
        alive        = [p for p in participants if not p.is_dead]
        counter_kills = []
        for p in alive:
            self._apply_counter(p, counter_dmg, damage_type)
            if p.is_dead:
                counter_kills.append(p.crew_name)

        self.db.add(ReIsolationLog(
            session_id=session.id, crew_id=crew_id,
            crew_roll=raw_roll, hit_bonus=weapon["hit_bonus"],
            final_roll=final_roll, threshold=threshold,
            success=success, damage_dealt=damage_dealt,
            counter_damage=counter_dmg,
        ))

        resolved, final_result = False, None
        if session.cargo_current_hp <= 0:
            session.status = ReIsolationStatus.RESOLVED
            self._isolate_cargo(cargo)
            final_result   = "success"
            resolved       = True
        elif not any(not p.is_dead for p in participants):
            session.status = ReIsolationStatus.RESOLVED
            final_result   = "fail"
            resolved       = True

        self.db.commit()
        return {
            "crew_name":        crew.crew_name,
            "weapon":           weapon["name"],
            "crew_roll":        raw_roll,
            "hit_bonus":        weapon["hit_bonus"],
            "final_roll":       final_roll,
            "threshold":        threshold,
            "success":          success,
            "damage_dealt":     damage_dealt,
            "cargo_hp":         f"{session.cargo_current_hp}/{session.cargo_max_hp}",
            "counter_damage":   counter_dmg,
            "damage_type":      damage_type,
            "counter_kills":    counter_kills,
            "session_resolved": resolved,
            "final_result":     final_result,
        }

    # ── 재격리 패턴 적용 ──────────────────────────────────────────────────────

    def apply_pattern(
        self,
        session: ReIsolationSession,
        pattern_id: _uuid.UUID,
        crew_ids: list[_uuid.UUID],
        stat: str | None,
        response_success: bool | None,
    ) -> dict:
        """
        재격리 패턴 적용.
        - stat + crew_ids → 크루별 개별 주사위 판정
        - response_success → 대응지문 판정 (전역)
        - 둘 다: 대응지문 실패 → 전체 실패; 성공 → 주사위 결과 유지
        unconditional_effects 항상 적용, conditional은 크루별 결과에 따라 적용.
        """
        pattern = self.db.query(ReisolationPattern).filter(ReisolationPattern.id == pattern_id).first()
        if not pattern:
            return {"error": "패턴 없음"}

        cargo         = self.db.query(Cargo).filter(Cargo.id == session.cargo_id).first()
        target_crews  = self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []

        # ── 크루별 판정 결과 계산 ───────────────────────────────────────────
        roll_details: dict[str, dict] = {}
        crew_results: dict[_uuid.UUID, str | None] = {}

        for crew in target_crews:
            dice_result = None
            if stat:
                crew_stat  = max(1, int(getattr(crew, stat, 1) or 1))
                cargo_stat = int(getattr(cargo, stat, 15) or 15) if cargo else 15
                dice_max   = max(1, crew_stat * 5)
                roll       = random.randint(1, dice_max)
                roll_details[crew.crew_name] = {"roll": roll, "vs": cargo_stat, "dice": f"1d{dice_max}"}

                if roll > cargo_stat:
                    dice_result = "success"
                elif random.random() < (pattern.critical_fail_rate or 0.05):
                    dice_result = "critical_fail"
                else:
                    dice_result = "fail"

            # 대응지문 결과 결합
            if response_success is None:
                overall = dice_result          # 주사위만 (없으면 None)
            elif not response_success:
                overall = "critical_fail" if dice_result == "critical_fail" else "fail"
            else:
                overall = dice_result if dice_result else "success"

            crew_results[crew.id] = overall

        # ── 효과 적용 ─────────────────────────────────────────────────────
        effects_log:     list[str] = []
        resolve_triggered          = False

        # unconditional — 판정 무관 전체 적용
        for effect in (pattern.unconditional_effects or []):
            if self._apply_effect(effect, target_crews, effects_log):
                resolve_triggered = True

        # conditional — 크루별 결과에 따라 적용
        for crew in target_crews:
            result = crew_results.get(crew.id)
            if result == "success":
                effect_list = pattern.on_success_effects or []
            elif result == "critical_fail":
                effect_list = pattern.on_critical_fail_effects or []
            elif result == "fail":
                effect_list = pattern.on_fail_effects or []
            else:
                effect_list = []

            for effect in effect_list:
                if self._apply_effect(effect, [crew], effects_log):
                    resolve_triggered = True

        if resolve_triggered and session.status == ReIsolationStatus.ACTIVE:
            session.status = ReIsolationStatus.RESOLVED
            if cargo:
                self._isolate_cargo(cargo)

        self.db.commit()

        return {
            "pattern_name":   pattern.pattern_name,
            "roll_details":   roll_details,
            "crew_results":   {c.crew_name: crew_results.get(c.id) for c in target_crews},
            "effects_applied": effects_log,
            "resolved":        resolve_triggered,
        }

    def _apply_effect(self, effect: dict, targets: list[Crew], log: list[str]) -> bool:
        """효과 1개 적용. resolve 트리거 시 True 반환."""
        etype  = effect.get("type")
        tmode  = effect.get("target", "random")
        alive  = [c for c in targets if not c.is_dead]

        if not alive and etype != "resolve":
            return False

        selected = [random.choice(alive)] if tmode == "random" else alive

        if etype == "instant_kill":
            for crew in selected:
                crew.hp         = 0
                crew.is_dead    = True
                crew.death_time = datetime.now(timezone.utc)
                log.append(f"{crew.crew_name} 즉사")

        elif etype == "status_effect":
            se_id = effect.get("status_effect_id")
            if se_id:
                for crew in selected:
                    self.db.add(CrewStatusEffect(
                        crew_id=crew.id,
                        status_effect_id=_uuid.UUID(se_id),
                    ))
                    log.append(f"{crew.crew_name} 상태이상 부여")

        elif etype == "damage":
            amount    = int(effect.get("amount") or 0)
            dtype_str = effect.get("damage_type", "hp")
            dtype     = DamageType(dtype_str) if dtype_str in DamageType._value2member_map_ else DamageType.HP
            for crew in selected:
                self._apply_counter(crew, amount, dtype)
                log.append(f"{crew.crew_name} -{amount} {dtype_str.upper()}")

        elif etype == "resolve":
            log.append("상황 해결 — 재격리 완료")
            return True

        return False

    def _get_participants(self, session: ReIsolationSession) -> list[Crew]:
        crew_ids = [
            sc.crew_id for sc in
            self.db.query(ReIsolationSessionCrew)
            .filter(ReIsolationSessionCrew.session_id == session.id).all()
        ]
        return self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []

    def _isolate_cargo(self, cargo: Cargo) -> None:
        """화물 격리 처리: is_escaped=False + 해당 화물 참조 상태이상 전부 해제."""
        cargo.is_escaped = False
        se_ids = [
            row.id for row in
            self.db.query(StatusEffect).filter(StatusEffect.cargo_id == cargo.id).all()
        ]
        if se_ids:
            self.db.query(CrewStatusEffect).filter(
                CrewStatusEffect.status_effect_id.in_(se_ids)
            ).delete(synchronize_session=False)

    def _apply_counter(self, crew: Crew, amount: int, damage_type: DamageType) -> None:
        if damage_type == DamageType.BOTH:
            hp_dmg, sp_dmg = amount // 2, amount - amount // 2
        elif damage_type == DamageType.HP:
            hp_dmg, sp_dmg = amount, 0
        else:
            hp_dmg, sp_dmg = 0, amount

        if hp_dmg:
            crew.hp = max(0, (crew.hp or 0) - hp_dmg)
            if crew.hp <= 0 and not crew.is_dead:
                crew.is_dead    = True
                crew.death_time = datetime.now(timezone.utc)
        if sp_dmg and not crew.is_dead:
            crew.sp = max(0, (crew.sp or 0) - sp_dmg)


# ── 승무원 vs 승무원 전투 ─────────────────────────────────────────────────────

def crew_vs_crew_combat(db: Session, crew_a_id: _uuid.UUID, crew_b_id: _uuid.UUID) -> dict:
    """행운 + 무기 보정 대항. 높은 쪽이 승리, 상대에게 무기 데미지 적용."""
    crew_a = db.query(Crew).filter(Crew.id == crew_a_id).first()
    crew_b = db.query(Crew).filter(Crew.id == crew_b_id).first()
    if not crew_a or not crew_b:
        return {"error": "승무원 없음"}

    weapon_a = get_equipped_weapon(db, crew_a_id)
    weapon_b = get_equipped_weapon(db, crew_b_id)

    roll_a = _roll_with_weapon(crew_a, weapon_a)
    roll_b = _roll_with_weapon(crew_b, weapon_b)
    a_wins = roll_a >= roll_b

    winner, loser   = (crew_a, crew_b) if a_wins else (crew_b, crew_a)
    weapon_w        = weapon_a if a_wins else weapon_b

    damage  = random.randint(max(1, weapon_w["damage_min"]), max(1, weapon_w["damage_max"]))
    loser.hp = max(0, (loser.hp or 0) - damage)
    if loser.hp <= 0 and not loser.is_dead:
        loser.is_dead    = True
        loser.death_time = datetime.now(timezone.utc)

    db.commit()
    return {
        "crew_a":       crew_a.crew_name,
        "roll_a":       roll_a,
        "weapon_a":     weapon_a["name"],
        "crew_b":       crew_b.crew_name,
        "roll_b":       roll_b,
        "weapon_b":     weapon_b["name"],
        "winner":       winner.crew_name,
        "loser":        loser.crew_name,
        "damage":       damage,
        "loser_hp":     loser.hp,
        "loser_killed": loser.is_dead,
    }
