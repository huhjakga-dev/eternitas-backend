import random
from datetime import date, datetime
from sqlalchemy.orm import Session

from .models import WorkSession, PrecursorLog, WorkLog
from src.runners.models import Crew, Runner
from src.common.schema import WorkStatus, DamageType
from src.common.utils import BandClient


class WorkService:
    def __init__(self, db: Session):
        self.db = db
        self.band = BandClient()

    # ------------------------------------------------------------------ #
    # [스케줄] 오늘 작업 세션 수집 (9:11, 10:11 실행)
    # ------------------------------------------------------------------ #

    async def collect_today_works(self):
        """
        밴드에서 오늘 올라온 [작업] 태그 게시글을 수집해 WorkSession으로 등록.
        이미 DB에 있는 post_key는 건너뜀.
        """
        all_posts = await self.band.get_posts()
        today = date.today()
        new_sessions = []

        for post in all_posts:
            post_date = datetime.fromtimestamp(post["created_at"] / 1000).date()

            if post_date != today or "[작업]" not in post.get("content", ""):
                continue

            exists = (
                self.db.query(WorkSession)
                .filter(WorkSession.post_key == post["post_key"])
                .first()
            )
            if exists:
                continue

            cargo_id = self._extract_cargo_id(post["content"])
            session = WorkSession(
                post_key=post["post_key"],
                cargo_id=cargo_id,
                status=WorkStatus.WAITING_PRECURSOR,
            )
            self.db.add(session)
            new_sessions.append(session)

        self.db.commit()
        return new_sessions

    # ------------------------------------------------------------------ #
    # [Polling] 전조 선언 처리 (WAITING_PRECURSOR 상태)
    # ------------------------------------------------------------------ #

    async def handle_precursor_declaration(self, session: WorkSession, comment: dict):
        """
        [선언] 댓글 감지 시:
        1. PrecursorLog 생성 (declaration_comment_id 저장)
        2. 밴드에 전조 감지 댓글 게시
        3. 세션 상태 → PRECURSOR_ACTIVE
        """
        # 중복 체크
        duplicate = (
            self.db.query(PrecursorLog)
            .filter(PrecursorLog.declaration_comment_id == comment["comment_key"])
            .first()
        )
        if duplicate:
            return

        pattern_id = self._match_pattern_via_llm(comment["content"])

        new_log = PrecursorLog(
            session_id=session.id,
            pattern_id=pattern_id,
            declaration_comment_id=comment["comment_key"],
        )
        self.db.add(new_log)
        session.status = WorkStatus.PRECURSOR_ACTIVE
        self.db.commit()

        await self.band.post_comment(
            session.post_key,
            "⚠️ 전조 현상이 관측되었습니다. 승무원은 [대응]하십시오.",
        )

    # ------------------------------------------------------------------ #
    # [Polling] 승무원 대응 처리 (PRECURSOR_ACTIVE 상태)
    # ------------------------------------------------------------------ #

    async def handle_crew_response(self, session: WorkSession, comment: dict):
        """
        [대응] 댓글 감지 시:
        1. 성패 판정 및 보정치 계산
        2. PrecursorLog 업데이트 (result, response_comment_id)
        3. 세션에 precursor_effect 저장
        4. 밴드에 결과 댓글 게시
        5. 세션 상태 → MAIN_WORK_READY
        """
        # 중복 체크
        duplicate = (
            self.db.query(PrecursorLog)
            .filter(PrecursorLog.response_comment_id == comment["comment_key"])
            .first()
        )
        if duplicate:
            return

        pre_log = (
            self.db.query(PrecursorLog)
            .filter(
                PrecursorLog.session_id == session.id,
                PrecursorLog.result == None,  # 아직 판정 안 된 로그
            )
            .first()
        )
        if not pre_log:
            return

        is_success = self._judge_success(pre_log.pattern_id, comment["content"])
        pre_log.result = "success" if is_success else "fail"
        pre_log.response_comment_id = comment["comment_key"]

        session.precursor_effect = self._calculate_modifiers(
            pre_log.result, pre_log.pattern_id
        )
        session.status = WorkStatus.MAIN_WORK_READY
        self.db.commit()

        msg = (
            "✅ 대응 성공! 작업 보정치가 적용됩니다."
            if is_success
            else "❌ 대응 실패! 패널티가 적용됩니다."
        )
        await self.band.post_comment(session.post_key, msg)

    # ------------------------------------------------------------------ #
    # [Polling] 본 작업 처리 (MAIN_WORK_READY 상태)
    # ------------------------------------------------------------------ #

    async def handle_main_work_execution(self, session: WorkSession, comment: dict):
        """
        [작업] 댓글 감지 시:
        1. 작업 명령 파싱 ("체력 5회 지력 3회" → [{"stat": "str", "count": 5}, ...])
        2. 스탯별 N회 다이스 시뮬레이션
        3. WorkLog 생성 및 승무원 HP 차감
        4. 밴드에 작업 결과 댓글 게시
        5. 중단 시 세션 상태 → RESOLVED
        """
        commands = self._parse_work_commands(comment["content"])
        crew = self._get_crew_by_band_user(comment["author"]["user_key"])
        if not crew:
            return

        modifiers = session.precursor_effect or {}
        total_summary = []
        interrupted = False

        for cmd in commands:
            if interrupted:
                break

            turn_logs = []
            success_count, dmg_total, actual_count = 0, 0, 0

            for i in range(1, cmd["count"] + 1):
                actual_count += 1
                stat_val = getattr(crew, cmd["stat"], 0) or 0
                buff = modifiers.get(f"{cmd['stat']}_buff", 0)
                crew_roll = random.randint(1, 20) + stat_val + buff
                cargo_roll = random.randint(1, 20) + 15  # 화물 기본 수치

                if crew_roll >= cargo_roll:
                    success_count += 1
                    turn_logs.append(
                        f"第{i}턴: 성공 (승무원 {crew_roll} vs 화물 {cargo_roll})"
                    )
                else:
                    dmg = (cargo_roll - crew_roll) * 2
                    dmg_total += dmg
                    crew.hp -= dmg
                    turn_logs.append(
                        f"第{i}턴: 실패 (승무원 {crew_roll} vs 화물 {cargo_roll}) → HP -{dmg}"
                    )

                    if crew.hp <= 0:
                        crew.hp = 0
                        turn_logs.append("🚨 승무원의 HP가 0이 되었습니다. 작업이 강제 중단됩니다.")
                        interrupted = True
                        break

            new_work = WorkLog(
                session_id=session.id,
                crew_id=crew.id,
                stat_type=cmd["stat"],
                planned_count=cmd["count"],
                actual_count=actual_count,
                success_count=success_count,
                damage_taken=dmg_total,
                damage_type=DamageType.HP,
                is_interrupted=interrupted,
            )
            self.db.add(new_work)

            summary = f"📊 [{cmd['stat'].upper()}] 작업 보고\n" + "\n".join(turn_logs)
            total_summary.append(summary)

        if interrupted:
            session.status = WorkStatus.RESOLVED

        self.db.commit()

        await self.band.post_comment(session.post_key, "\n\n".join(total_summary))

    # ------------------------------------------------------------------ #
    # 내부 헬퍼 메서드
    # ------------------------------------------------------------------ #

    def _extract_cargo_id(self, content: str) -> int:
        """
        게시글 내용에서 화물 ID를 파싱.
        TODO: LLM(ollama lfm) 연동으로 화물명 → ID 변환
        """
        return 1

    def _match_pattern_via_llm(self, _content: str) -> int:
        """
        [선언] 댓글 내용으로 화물 패턴 ID 매칭.
        TODO: LLM 연동
        """
        return 1

    def _judge_success(self, _pattern_id: int, _content: str) -> bool:
        """
        [대응] 댓글 내용과 패턴을 비교해 성패 판정.
        TODO: LLM 연동
        """
        return True

    def _calculate_modifiers(self, result: str, _pattern_id: int) -> dict:
        """
        전조 결과에 따른 보정치 계산.
        반환 예: {"str_buff": 2, "int_buff": -1}
        TODO: CargoPattern 테이블의 buff_stat_json / debuff_stat_json 참조
        """
        return {"str_buff": 2} if result == "success" else {"str_buff": -2}

    def _parse_work_commands(self, _content: str) -> list[dict]:
        """
        작업 명령 파싱: "체력 5회 지력 3회" → [{"stat": "str", "count": 5}, ...]
        TODO: LLM 연동으로 자연어 파싱 개선
        """
        return [{"stat": "str", "count": 5}]

    def _get_crew_by_band_user(self, band_user_key: str):
        """밴드 유저 키로 Crew 조회"""
        runner = (
            self.db.query(Runner)
            .filter(Runner.band_user_id == band_user_key)
            .first()
        )
        if not runner:
            return None
        return (
            self.db.query(Crew)
            .filter(Crew.runner_id == runner.id)
            .first()
        )
