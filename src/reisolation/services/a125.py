"""
화물: A-125 재격리 서비스
DB에 등록해야 하는 항목:
  - ReisolationPattern: "A-125 재격리 패턴 1"
  - ReisolationPattern: "A-125 재격리 패턴 2"
  - StatusEffect: "보육"   (cargo_id=이 화물, luckiness:-1)
  - StatusEffect: "몽상"   (cargo_id=이 화물, luckiness:-1, SP 10분당 5 데미지)
"""
import uuid
from src.runners.models import Crew
from src.reisolation.models import ReisolationPattern
from .base import BaseReisolationService


class A125ReisolationService(BaseReisolationService):
    _P_CHILDREN = "A-125 재격리 패턴 1"
    _P_NAP      = "A-125 재격리 패턴 2"
    _SE_NURTURE = "보육"
    _SE_DREAM   = "몽상"

    def run_pattern(
        self,
        pattern_id: uuid.UUID,
        crew_ids: list[uuid.UUID],
        stat: str | None,
        response_success: bool | None,
    ) -> dict:
        pattern = self.db.query(ReisolationPattern).filter(ReisolationPattern.id == pattern_id).first()
        if not pattern:
            return {"log": ["패턴을 찾을 수 없습니다."], "resolved": False}

        target_crews = self.db.query(Crew).filter(Crew.id.in_(crew_ids)).all() if crew_ids else []
        alive        = [c for c in target_crews if not c.is_dead]

        if pattern.pattern_name == self._P_CHILDREN:
            return self._pattern_children(response_success, alive)
        elif pattern.pattern_name == self._P_NAP:
            return self._pattern_nap(response_success, alive)
        else:
            from .base import GenericReisolationService
            return GenericReisolationService(self.db, self.session, self.cargo).run_pattern(
                pattern_id, crew_ids, stat, response_success
            )

    # ── 재격리 패턴 1: 아이들의 소리 ─────────────────────────────────────────

    def _pattern_children(self, response_success: bool | None, alive: list[Crew]) -> dict:
        log = [
            "■ A-125 — 재격리 패턴 1",
            "",
            "아이들이 웃으며 활기차게 뛰어다니는 소리가 들려옵니다.",
            "그 모습이 어쩐지 눈 앞에 아른거리는 느낌이라⋯ 마음이 좋아집니다.",
            "",
        ]

        if response_success:
            log += [
                "자신의 뺨을 때리거나, 눈을 문지르는 등 정신을 붙잡으려는 행동.",
                "→ 대응 성공 — 효과 없음.",
            ]
            return {"log": log, "resolved": False}

        log += [
            "아아, 과연 저 아이들은 커서 어떤 어른이 될까요?",
            "올바르게 성장한 아이들을 떠올리자면 벌써부터 가슴이 두근두근거립니다.",
            "아! 물론, 그렇다고 해서 교육을 서두를 수는 없는 노릇이죠.",
            "아이들이 엇나가지 않도록 똑바로 이끌어 주어야 해요.",
            "그것이 선생님의 역할이니까요.",
            "",
        ]
        for crew in alive:
            log.append(f"→ {self.apply_se(crew, self._SE_NURTURE)}")

        return {"log": log, "resolved": False, "status_effect": self._SE_NURTURE}

    # ── 재격리 패턴 2: 자장가 ────────────────────────────────────────────────

    def _pattern_nap(self, response_success: bool | None, alive: list[Crew]) -> dict:
        log = [
            "■ A-125 — 재격리 패턴 2",
            "",
            "⋯문득, 머릿속에 한 생각이 스칩니다. 지금 몇 시였죠?",
            "이런, 낮잠을 잘 시간이네요. 하마터면 까먹을 뻔 했어요.",
            "때마침 선생님이 들려주는 고요한 자장가가 들려오네요.",
            "",
        ]

        if response_success:
            log += [
                "귀를 막거나 자장가를 방해하는 행동.",
                "→ 대응 성공 — 효과 없음.",
            ]
            return {"log": log, "resolved": False}

        log += [
            "잠시 눈을 감고서 안온한 꿈의 세계로 향합니다.",
            "그동안 호기심과 명랑함은 잠시 내려두기로 해요!",
            "",
        ]
        for crew in alive:
            log.append(f"→ {self.apply_se(crew, self._SE_DREAM)}")

        return {"log": log, "resolved": False, "status_effect": self._SE_DREAM}
