import random
from datetime import date, datetime
from sqlalchemy.orm import Session

from .models import WorkSession, PrecursorLog, WorkLog, WorkSessionCrew
from src.runners.models import Crew, Runner, CargoPattern
from src.common.schema import WorkStatus, DamageType
from src.common.utils import BandClient, OllamaClient, GeminiClient


class WorkService:
    def __init__(self, db: Session):
        self.db = db
        self.band = BandClient()
        self.llm = OllamaClient()
        self.gemini = GeminiClient()

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

            cargo_id = await self._extract_cargo_id(post["content"])
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
        1. 해당 화물의 CargoPattern 조회 (comment.content에 패턴 아이디 단일 선언해서 사용)
        2. PrecursorLog 생성 (declaration_comment_id 저장)
        3. 밴드에 전조 감지 댓글 게시
        4. 세션 상태 → PRECURSOR_ACTIVE
        """
        # 중복 체크
        duplicate = (
            self.db.query(PrecursorLog)
            .filter(PrecursorLog.declaration_comment_id == comment["comment_key"])
            .first()
        )
        if duplicate:
            return

        # 화물의 [선언] 댓글 내용에서 패턴 조회 (cargo_id 기준 1:1)
        cargo_pattern = (
            self.db.query(CargoPattern)
            .filter(CargoPattern.cargo_id == session.cargo_id)
            .first()
        )
        pattern_id = cargo_pattern.id if cargo_pattern else None

        new_log = PrecursorLog(
            session_id=session.id,
            pattern_id=pattern_id,
            declaration_comment_id=comment["comment_key"],
        )
        self.db.add(new_log)
        session.status = WorkStatus.PRECURSOR_ACTIVE
        self.db.commit()

        # description을 시스템 계정이 밴드에 전조 현상으로 게시
        if cargo_pattern and cargo_pattern.description:
            notice = (
                f"⚠️ [전조 현상 감지]\n"
                f"{cargo_pattern.description}\n\n"
                f"승무원은 [대응] 댓글로 대응하십시오."
            )
        else:
            notice = "⚠️ 전조 현상이 감지되었습니다. 승무원은 [대응]하십시오."

        await self.band.post_comment(session.post_key, notice)

    # ------------------------------------------------------------------ #
    # [Polling] 승무원 대응 처리 (PRECURSOR_ACTIVE 상태)
    # ------------------------------------------------------------------ #

    async def handle_crew_response(self, session: WorkSession, comment: dict):
        """
        [대응] 댓글 감지 시:
        1. LLM으로 대응 성패 판정 (success / fail / critical_fail)
        2. PrecursorLog 업데이트 (result, response_comment_id)
        3. 세션에 precursor_effect 보정치 저장
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

        crew = self._get_crew_by_band_user(comment["author"]["user_key"])
        result = await self._judge_success(pre_log.pattern_id, comment["content"], crew)
        pre_log.result = result
        pre_log.crew_id = crew.id if crew else None
        pre_log.response_comment_id = comment["comment_key"]

        session.precursor_effect = self._calculate_modifiers(result, pre_log.pattern_id)
        session.status = WorkStatus.MAIN_WORK_READY
        self.db.commit()

        if result == "success":
            msg = "✅ 대응 성공! 작업 보정치가 적용됩니다."
        elif result == "critical_fail":
            msg = "💀 대실패! 중대 패널티가 적용됩니다."
        else:
            msg = "❌ 대응 실패! 패널티가 적용됩니다."

        await self.band.post_comment(session.post_key, msg)

    # ------------------------------------------------------------------ #
    # [Polling] 본 작업 처리 (MAIN_WORK_READY 상태)
    # ------------------------------------------------------------------ #

    async def handle_main_work_execution(self, session: WorkSession, comment: dict):
        """
        [작업] 댓글 감지 시:
        1. LLM으로 작업 명령 파싱 ("체력 5회 지력 3회" → 구조화)
        2. 스탯별 N회 다이스 시뮬레이션
        3. WorkLog 생성 및 승무원 HP 차감
        4. 밴드에 작업 결과 댓글 게시
        5. 중단 시 세션 상태 → RESOLVED
        """
        commands = await self._parse_work_commands(comment["content"])
        crew = self._get_crew_by_band_user(comment["author"]["user_key"])
        if not crew:
            return

        # 세션 참여 승무원 목록 조회 (데미지 분산용)
        session_crew_ids = [
            sc.crew_id for sc in
            self.db.query(WorkSessionCrew)
            .filter(WorkSessionCrew.session_id == session.id)
            .all()
        ]
        participant_count = max(len(session_crew_ids), 1)

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
                    raw_dmg = (cargo_roll - crew_roll) * 2
                    # 데미지를 참여 승무원 수로 분산 (작업자 본인 포함)
                    shared_dmg = max(1, raw_dmg // participant_count)
                    dmg_total += shared_dmg
                    crew.hp -= shared_dmg
                    split_note = f" (전체 {raw_dmg} → {participant_count}명 분산)" if participant_count > 1 else ""
                    turn_logs.append(
                        f"第{i}턴: 실패 (승무원 {crew_roll} vs 화물 {cargo_roll}) → HP -{shared_dmg}{split_note}"
                    )

                    if crew.hp <= 0:
                        crew.hp = 0
                        turn_logs.append(
                            "🚨 승무원의 HP가 0이 되었습니다. 작업이 강제 중단됩니다."
                        )
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
    # 내부 헬퍼 메서드 (LLM 연동)
    # ------------------------------------------------------------------ #

    async def _extract_cargo_id(self, content: str) -> int:
        """
        게시글 내용에서 화물명을 파악해 DB에서 cargo_id 조회.
        LLM이 화물명을 추출 → DB lookup.
        """
        from src.runners.models import Cargo

        cargos = self.db.query(Cargo).all()
        if not cargos:
            return 1

        cargo_list = "\n".join([f"ID:{c.id} 이름:{c.cargo_name}" for c in cargos])
        prompt = (
            f"아래 게시글에서 언급된 화물의 ID를 숫자만 답해줘.\n"
            f"화물 목록:\n{cargo_list}\n"
            f"게시글: {content}\n"
            f"ID:"
        )
        raw = await self.llm.generate(prompt)
        try:
            return int(raw.strip().split()[0])
        except (ValueError, IndexError):
            return cargos[0].id

    async def _judge_success(self, pattern_id: int | None, content: str, crew=None) -> str:
        """
        전조 대응 판정 로직:
          - 스탯 판정(주사위): crew의 luckiness 기반 1d20 롤
          - 행동 판정(Claude): 대응 내용 vs 정답 의미 비교

          결과 조합:
            스탯 성공 + 행동 성공  → success
            둘 중 하나 실패       → 50% success / 50% fail
            둘 다 실패            → fail
          + instant_kill_rate 확률로 critical_fail (fail일 때만 적용)
        """
        if pattern_id is None:
            return "fail"

        pattern = self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        if not pattern:
            return "fail"

        # 1. 스탯 판정: luckiness 기반 1d20
        luck_val = getattr(crew, "luckiness", 1) or 1
        stat_roll = random.randint(1, 20) + luck_val
        stat_success = stat_roll >= 15  # 기준선 15

        # 2. 행동 판정: Claude
        action_result = await self.gemini.judge_response(
            pattern_name=pattern.pattern_name or "",
            description=pattern.description or "",
            answer=pattern.answer or "",
            crew_response=content,
        )
        action_success = action_result == "action_success"

        # 3. 결과 조합
        if stat_success and action_success:
            result = "success"
        elif stat_success or action_success:
            result = "success" if random.random() < 0.5 else "fail"
        else:
            result = "fail"

        # 4. 대실패 확률 적용 (fail일 때만)
        if result == "fail":
            kill_rate = pattern.instant_kill_rate or 0.0
            if kill_rate > 0 and random.random() < kill_rate:
                result = "critical_fail"

        return result

    def _calculate_modifiers(self, result: str, pattern_id: int | None) -> dict:
        """
        전조 결과에 따라 CargoPattern의 buff/debuff JSON 반환.
        """
        if pattern_id is None:
            return {}

        pattern = (
            self.db.query(CargoPattern).filter(CargoPattern.id == pattern_id).first()
        )
        if not pattern:
            return {}

        if result == "success":
            return pattern.buff_stat_json or {}
        return pattern.debuff_stat_json or {}

    async def _parse_work_commands(self, content: str) -> list[dict]:
        """
        [작업] 댓글에서 스탯별 횟수를 파싱.
        예: "체력 5회 지력 3회" → [{"stat":"strength","count":5},{"stat":"inteligence","count":3}]

        스탯 매핑 (DB 컬럼명 기준):
          체력/힘/근력/STR → strength
          지력/지능/INT    → inteligence  (DB 오타 그대로)
          행운/럭/LUC      → luckiness
        """
        prompt = (
            "작업 명령 텍스트를 JSON 배열로만 변환해줘.\n"
            "스탯 매핑: 체력/힘/근력/STR=strength, 지력/지능/INT=inteligence, 행운/럭/LUC=luckiness\n"
            '예시 입력: "체력 5회 지력 3회"\n'
            '예시 출력: [{"stat":"strength","count":5},{"stat":"inteligence","count":3}]\n'
            f'입력: "{content}"\n'
            "출력:"
        )
        result = await self.llm.parse_json(prompt)
        if isinstance(result, list) and result:
            return result
        # 파싱 실패 시 폴백: 체력 1회
        return [{"stat": "strength", "count": 1}]

    def _get_crew_by_band_user(self, band_user_key: str):
        """
        밴드 유저 키 → Runner → Crew 조회.
        테스트용: '__crew_id__<uuid>' 형식이면 crew_id로 직접 조회.
        """
        import uuid as _uuid
        if band_user_key.startswith("__crew_id__"):
            crew_id_str = band_user_key.removeprefix("__crew_id__")
            try:
                return self.db.query(Crew).filter(Crew.id == _uuid.UUID(crew_id_str)).first()
            except ValueError:
                return None

        runner = (
            self.db.query(Runner).filter(Runner.band_user_id == band_user_key).first()
        )
        if not runner:
            return None
        return self.db.query(Crew).filter(Crew.runner_id == runner.id).first()
