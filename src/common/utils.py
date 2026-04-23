import random
from sqlalchemy.orm import Session

_HP_MULT = {0: 1.0, 1: 1.0, 2: 1.1, 3: 1.3, 4: 1.5}
_SP_MULT = {0: 1.0, 1: 1.0, 2: 0.8, 3: 0.6, 4: 0.5}


def compute_max_caps(
    health: int,
    mentality: int,
    mechanization_lv: int,
    initial_mechanization_lv: int = 0,
) -> tuple[int, int]:
    """
    초기 단계 이상으로 올랐을 때만 현재 단계 효과 적용.
    초기 단계와 같으면 효과 없음(1.0x).
    ex) 초기 lv3(효과없음) → 부활 lv4 → 바로 lv4 효과(1.5x) 적용.
    """
    mech   = mechanization_lv or 0
    init   = initial_mechanization_lv or 0
    eff_lv = mech if mech > init else 0
    max_hp = round((10 + health * 5) * _HP_MULT.get(eff_lv, 1.5))
    max_sp = round(mentality * 5 * _SP_MULT.get(eff_lv, 0.5))
    return max_hp, max_sp


# ── 판정 유틸리티 ──────────────────────────────────────────────────────────────

def roll_vs_cargo(crew_stat: int, cargo_fixed: int) -> dict:
    """화물/승무원 대항: 승무원 1d(5×stat) vs 화물 고정값. 승무원 >= 화물이면 성공."""
    crew_roll = random.randint(1, max(1, crew_stat * 5))
    return {"crew_roll": crew_roll, "cargo_fixed": cargo_fixed, "success": crew_roll >= cargo_fixed}


def roll_solo(crew_stat: int, threshold: int) -> dict:
    """캐릭터 어필: 1d(5×stat) vs 고정 성공치."""
    roll = random.randint(1, max(1, crew_stat * 5))
    return {"roll": roll, "threshold": threshold, "success": roll >= threshold}


def roll_vs_crew(stat_a: int, stat_b: int) -> dict:
    """승무원 대항: 각 1d(5×stat), a >= b이면 a 승리."""
    roll_a = random.randint(1, max(1, stat_a * 5))
    roll_b = random.randint(1, max(1, stat_b * 5))
    return {"roll_a": roll_a, "roll_b": roll_b, "a_wins": roll_a >= roll_b}


def get_equipped_weapon(db: Session, crew_id) -> dict:
    """착용 중인 무기 전투 스탯. 미착용 시 기본값."""
    from src.runners.models import CrewEquipment, Equipment  # noqa: PLC0415
    row = (
        db.query(CrewEquipment, Equipment)
        .join(Equipment, Equipment.id == CrewEquipment.equipment_id)
        .filter(
            CrewEquipment.crew_id == crew_id,
            CrewEquipment.is_equipped == True,
            Equipment.equipment_type == "weapon",
        )
        .first()
    )
    if row:
        _, eq = row
        eff = eq.effects or {}
        return {
            "name":       eq.name,
            "hit_bonus":  int(eff.get("hit_bonus", 0)),
            "damage_min": int(eff.get("damage_min", 1)),
            "damage_max": int(max(eff.get("damage_max", 1), eff.get("damage_min", 1))),
            "min_roll":   int(eff.get("min_roll", 0)),
        }
    return {"name": None, "hit_bonus": 0, "damage_min": 1, "damage_max": 3, "min_roll": 0}
