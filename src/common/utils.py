import httpx
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
