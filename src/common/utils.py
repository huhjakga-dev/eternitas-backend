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
