from pydantic import BaseModel
from typing import Optional


class CreateReIsolationSession(BaseModel):
    cargo_id:  str
    crew_ids:  list[str] = []


class ReIsolationAttack(BaseModel):
    crew_id: str


# ── 재격리 패턴 ───────────────────────────────────────────────────────────────

class EffectAction(BaseModel):
    """단일 효과 액션.
    type: instant_kill | status_effect | damage | resolve
    target: random (대상 중 랜덤 1명) | all (대상 전원)
    """
    type:             str
    target:           str            = "random"
    status_effect_id: Optional[str] = None   # status_effect 전용
    amount:           Optional[int] = None   # damage 전용
    damage_type:      Optional[str] = None   # damage 전용 (hp/sp/both)


class CreateReisolationPattern(BaseModel):
    cargo_id:                str
    pattern_name:            str
    description:             Optional[str]       = None
    stat:                    Optional[str]       = None
    critical_fail_rate:      float               = 0.05
    unconditional_effects:   list[EffectAction]  = []
    on_success_effects:      list[EffectAction]  = []
    on_fail_effects:         list[EffectAction]  = []
    on_critical_fail_effects: list[EffectAction] = []


class ApplyPatternBody(BaseModel):
    """재격리 패턴 적용 요청.
    - stat + crew_ids 동시 존재 → 주사위 대항 판정 (크루별 개별 판정)
    - response_success 존재 → 대응지문 판정 결과 (전체 적용)
    - 둘 다 존재 → 대응지문 실패 시 전체 실패; 성공 시 주사위 결과 유지
    - 둘 다 없음 → unconditional_effects만 적용
    """
    pattern_id:       str
    crew_ids:         list[str]
    stat:             Optional[str]  = None
    response_success: Optional[bool] = None
