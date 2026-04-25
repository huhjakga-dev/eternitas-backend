"""
화물: A-125
DB에 등록해야 하는 항목:
  - CargoPattern: "A-125 관리 패턴 1"
  - CargoPattern: "A-125 관리 패턴 2"
"""
import uuid
from src.runners.models import Crew, CargoPattern
from src.common.schema import WorkStatus
from src.common.utils import compute_max_caps
from .base import BaseCargoService


class A125Service(BaseCargoService):
    _P_GREET   = "A-125 관리 패턴 1"
    _P_MANNERS = "A-125 관리 패턴 2"

    def run_precursor(self, pattern_id: uuid.UUID, result: str, crew: Crew) -> dict:
        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {"log": ["패턴을 찾을 수 없습니다."], "resolved": False}

        if pattern.pattern_name == self._P_GREET:
            return self._pattern_greet(result, crew)
        elif pattern.pattern_name == self._P_MANNERS:
            return self._pattern_manners(result, crew)
        else:
            return {
                "log": [f"'{pattern.pattern_name}' 패턴에 대한 서비스 함수가 없습니다."],
                "resolved": False,
            }

    # ── 공통 스탯 수정 ────────────────────────────────────────────────────────

    def _modify_stat(self, crew: Crew, stat: str, delta: int) -> str:
        current = getattr(crew, stat) or 1
        setattr(crew, stat, max(1, current + delta))
        if stat in ("health", "mentality"):
            mhp, msp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv or 0, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp, crew.max_sp = mhp, msp
        sign = f"+{delta}" if delta > 0 else str(delta)
        return f"{crew.crew_name} {stat} {sign} (판정 수치 {'+' if delta > 0 else ''}{delta * 5})"

    # ── 관리 패턴 1: 안녕, 아가야? ───────────────────────────────────────────

    def _pattern_greet(self, result: str, crew: Crew) -> dict:
        log = [
            f"  대상: {crew.crew_name}",
            "",
            "안녕, 아가야? 이리 만나게 되어 기쁘구나.",
            "오늘은 무얼 하며 지냈는지 내게 이야기해주지 않으련?",
            "선생님은 네 이야기가 너무 궁금하단다.",
            "",
        ]

        if result == "success":
            msg = self._modify_stat(crew, "health", 1)
            log += [
                f"{crew.crew_name}이(가) 존댓말로 대답했다.",
                f"→ {msg}",
            ]
            self.session.status = WorkStatus.MAIN_WORK_READY
            return {"log": log, "resolved": False, "stat_change": {"health": 1}}

        else:  # fail / critical_fail
            msg = self._modify_stat(crew, "mentality", -1)
            log += [
                f"{crew.crew_name}이(가) 대답하지 않거나 반말을 사용했다.",
                f"→ {msg}",
            ]
            self.session.status = WorkStatus.MAIN_WORK_READY
            return {"log": log, "resolved": False, "stat_change": {"mentality": -1}}

    # ── 관리 패턴 2: 바른 인사 예절 ──────────────────────────────────────────

    def _pattern_manners(self, result: str, crew: Crew) -> dict:
        log = [
            f"  대상: {crew.crew_name}",
            "",
            "선생님은 아가가 사람들에게 이쁨을 받았으면 좋겠어요.",
            "자, 우리 함께 바른 인사 예절을 배워볼까요?",
            "",
        ]

        if result == "success":
            msg = self._modify_stat(crew, "inteligence", 1)
            log += [
                f"{crew.crew_name}이(가) 바른 예절을 보였다.",
                f"→ {msg}",
            ]
            self.session.status = WorkStatus.MAIN_WORK_READY
            return {"log": log, "resolved": False, "stat_change": {"inteligence": 1}}

        else:  # fail / critical_fail
            msg = self._modify_stat(crew, "mentality", -1)
            log += [
                f"{crew.crew_name}이(가) 무례한 답변을 했다.",
                f"→ {msg}",
            ]
            self.session.status = WorkStatus.MAIN_WORK_READY
            return {"log": log, "resolved": False, "stat_change": {"mentality": -1}}
