from sqlalchemy.orm import Session
from .models import CargoPrecursor


class PrecursorService:
    def __init__(self, db: Session):
        self.db = db
        self.band_token = "YOUR_BAND_TOKEN"

    async def register_batch_posts(self, posts: list):
        """10분 모집된 게시글들을 일괄 등록"""
        new_entries = []
        for post in posts:
            # LLM Logic: post.content에서 cargo_id 추출 (가정)
            cargo_id = self._extract_cargo_id_via_llm(post["content"])

            precursor = CargoPrecursor(
                post_key=post["post_key"], cargo_id=cargo_id, status="waiting"
            )
            self.db.add(precursor)
            new_entries.append(precursor)

        self.db.commit()
        return new_entries

    async def poll_and_update(self):
        """Active한 전조들만 타겟 폴링하여 상태 업데이트"""
        active_tasks = (
            self.db.query(CargoPrecursor)
            .filter(CargoPrecursor.status != "resolved")
            .all()
        )

        for task in active_tasks:
            # 1. 밴드에서 해당 post_key의 댓글 목록 GET
            comments = self._get_band_comments(task.post_key)

            if task.status == "waiting":
                # 화물 선언 [선언] 찾기
                for c in comments:
                    if "[선언]" in c["content"]:
                        # LLM: 패턴 매칭
                        pattern_id = self._match_pattern_via_llm(c["content"])
                        task.pattern_id = pattern_id
                        task.declaration_comment_id = c["comment_id"]
                        task.status = "active"
                        break

            elif task.status == "active":
                # 승무원 대응 [대응] 찾기
                for c in comments:
                    if (
                        "[대응]" in c["content"]
                        and c["comment_id"] != task.declaration_comment_id
                    ):
                        # 판정 로직 (패턴의 정답과 대응 내용 비교)
                        is_success = self._judge_success(task.pattern_id, c["content"])
                        task.result = "success" if is_success else "fail"
                        task.response_comment_id = c["comment_id"]
                        task.status = "resolved"

                        # 밴드에 최종 결과 댓글 작성 API 호출
                        self._post_result_to_band(task.post_key, task.result)
                        break

        self.db.commit()

    def _extract_cargo_id_via_llm(self, content):
        # TODO: OpenAI API 연동하여 본문에서 화물 ID 추출
        return 1

    def _get_band_comments(self, post_key):
        # 밴드 공식 API 호출: GET /v2/band/post/comments
        return []  # Mock 데이터
