from __future__ import annotations

import json
import re
import httpx
from google import genai
from src.config import settings  # BAND_ACCESS_TOKEN, BAND_KEY 등이 저장된 설정


class BandClient:
    BASE_URL = settings.BAND_BASE_URL

    def __init__(self):
        self.params = {
            "access_token": settings.BAND_ACCESS_TOKEN,
            "band_key": settings.BAND_KEY,
            "locale": "ko_KR",
        }

    async def get_posts(self):
        """최신 게시글 목록 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/posts", params=self.params)
            data = response.json()
            if data.get("result_code") == 1:
                return data["result_data"]["items"]
            return []

    async def get_comments(self, post_key: str):
        """특정 게시글의 댓글 목록 조회 (생성순)"""
        params = self.params.copy()
        params["post_key"] = post_key
        params["sort"] = "+created_at"

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/post/comments", params=params)
            data = response.json()
            if data.get("result_code") == 1:
                return data["result_data"]["items"]
            return []

    async def post_comment(self, post_key: str, body: str) -> bool:
        """게시글에 댓글 작성"""
        params = self.params.copy()
        params["post_key"] = post_key
        params["body"] = body

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/comment/create", params=params
            )
            data = response.json()
            return data.get("result_code") == 1


class GeminiClient:
    """
    전조 대응 판정 전용 Gemini 클라이언트.
    행동 내용이 정답과 의미상 일치하는지 판단한다.
    """

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def judge_response(
        self,
        pattern_name: str,
        description: str,
        answer: str,
        crew_response: str,
    ) -> str:
        """
        승무원의 대응이 정답과 일치하는지 판정.
        반환값: "action_success" | "action_fail"
        """
        prompt = (
            "너는 텍스트 RPG 판정 시스템이야. "
            "승무원의 대응이 정답 대응과 의미상 일치하면 'action_success', "
            "그렇지 않으면 'action_fail'만 출력해. 다른 말은 절대 하지 마.\n\n"
            f"전조 패턴: {pattern_name}\n"
            f"전조 현상: {description}\n"
            f"정답 대응: {answer}\n"
            f"승무원 대응: {crew_response}\n"
            f"판정:"
        )
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw = response.text.strip().lower()
        return "action_success" if "action_success" in raw else "action_fail"


class OllamaClient:
    """
    호스트에서 실행 중인 Ollama 서버와 통신.
    Docker 환경: host.docker.internal:11434
    로컬 실행: localhost:11434
    """

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL

    async def generate(self, prompt: str) -> str:
        """단순 텍스트 생성 (stream=false)"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            return response.json().get("response", "").strip()

    async def parse_json(self, prompt: str) -> list | dict | None:
        """JSON 결과가 필요한 생성. 실패 시 None 반환"""
        raw = await self.generate(prompt)
        try:
            match = re.search(r"[\[\{].*[\]\}]", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        return None
