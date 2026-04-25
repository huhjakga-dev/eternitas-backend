"""
화물: B-156
DB에 등록해야 하는 항목:
  - CargoPattern: "B-156 관리 패턴 1"
  - CargoPattern: "B-156 관리 패턴 2"
  - StatusEffect: "기억혼란"  (cargo_id=이 화물, stat_json: inteligence:-2)
"""
import uuid
from src.runners.models import Crew, CargoPattern
from .base import BaseCargoService


class SpreadingThirstService(BaseCargoService):
    _P_PHONE   = "B-156 관리 패턴 1"
    _P_CALL    = "B-156 관리 패턴 2"
    _SE_CONFUSION = "기억혼란" # 상태이상 이름

    def run_precursor(self, pattern_id: uuid.UUID, result: str, crew: Crew) -> dict:
        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return {"log": ["패턴을 찾을 수 없습니다."], "resolved": False}

        if pattern.pattern_name == self._P_PHONE:
            return self._pattern_phone(result, crew)
        elif pattern.pattern_name == self._P_CALL:
            return self._pattern_call(result, crew)
        else:
            return {
                "log": [f"'{pattern.pattern_name}' 패턴에 대한 서비스 함수가 없습니다."],
                "resolved": False,
            }

    # ── 관리법 1: 전화기 ──────────────────────────────────────────────────────

    def _pattern_phone(self, result: str, crew: Crew) -> dict:
        log = [
            f"  패턴: {self._P_PHONE}  |  대상: {crew.crew_name}",
            "",
            "격리실에 입장한 승무원들은 고풍스러운 외양의 다이얼식 전화기를 마주한다.",
            "전선이 달려있지 않음에도 불구하고, 전화가 걸려 오고 있다.",
            "",
        ]

        if result == "success":
            log += [
                f"{crew.crew_name}이(가) 전화를 받았다.",
                "",
                "→ 다음 전조 단계로 이어집니다.",
            ]
            return {"log": log, "resolved": False, "hint": self._P_CALL}

        elif result == "fail":
            self.force_fail()
            log += [
                "참여한 모든 승무원이 전화를 받지 않았다.",
                "전화기가 멈추고, 격리실에 무거운 침묵이 드리운다.",
                "",
                "→ 전체 작업 실패 처리.",
            ]
            return {"log": log, "resolved": True, "final_result": "fail"}

        elif result == "critical_fail":
            msg = self.kill(crew)
            log += [
                f"{crew.crew_name}이(가) 전화기를 물리적으로 공격했다.",
                "바닥에서 꼬챙이가 튀어나와 승무원을 꿰뚫었다.",
                f"→ {msg}",
            ]
            alive = self.get_alive_crews()
            if not alive:
                self.force_fail()
                log.append("생존 승무원 없음 — 작업 실패 처리.")
            return {
                "log": log,
                "resolved": not bool(alive),
                "final_result": "fail" if not alive else None,
                "killed": [crew.crew_name],
            }

        return {"log": [f"알 수 없는 결과: {result}"], "resolved": False}

    # ── 관리법 2: 통화 내용 ───────────────────────────────────────────────────

    def _pattern_call(self, result: str, crew: Crew) -> dict:
        log = [
            f"  패턴: {self._P_CALL}  |  대상: {crew.crew_name}",
            "",
            "대상 승무원의 비밀 설정을 포함한 화물의 질문들이 이어진다.",
            "",
        ]

        if result == "success":
            self.force_success()
            log += [
                f"{crew.crew_name}이(가) 모든 질문에 '아니오'라고 답했다.",
                "전화 연결음이 끊겼다. 전화기를 다시 걸어놓았다.",
                "",
                "→ 전체 작업 성공 처리.",
            ]
            return {"log": log, "resolved": True, "final_result": "success"}

        elif result in ("fail", "critical_fail"):
            log += [
                "통화 도중 허락의 뉘앙스가 감지되었다.",
                "정신력 대항 판정을 실시한다.",
                "",
            ]
            roll = self.roll_stat(crew, "mentality")
            log.append(
                f"정신력 굴림: {roll['crew_roll']} (1d{int(crew.mentality or 1) * 5})"
                f"  vs  화물 고정값 {roll['cargo_fixed']}"
                f"  →  {'성공' if roll['success'] else '실패'}"
            )

            if roll["success"]:
                se_msg = self.apply_se(crew, self._SE_CONFUSION)
                log += [
                    "",
                    "대항 성공 — 정신을 지켰으나 기억이 흐트러졌다.",
                    f"→ {se_msg}",
                    "  지력 스탯 -2 / 자신을 '백작'으로 지칭하는 행동 변화",
                ]
                return {
                    "log": log,
                    "resolved": False,
                    "status_effect": self._SE_CONFUSION,
                }
            else:
                msg = self.kill(crew)
                log += [
                    "",
                    f"대항 실패 — {crew.crew_name}이(가) 목소리에 잠식당했다.",
                    f"→ {msg}",
                ]
                alive = self.get_alive_crews()
                if alive:
                    log.append(
                        f"생존 승무원 {len(alive)}명 — "
                        "전화를 끝까지 받은 상태. 작업 계속 진행 가능."
                    )
                else:
                    self.force_fail()
                    log.append("전원 사망 — 작업 실패 처리.")
                return {
                    "log": log,
                    "resolved": not bool(alive),
                    "final_result": "fail" if not alive else None,
                    "killed": [crew.crew_name],
                }

        return {"log": [f"알 수 없는 결과: {result}"], "resolved": False}
