FROM python:3.12-slim

# uv 바이너리만 복사 (가벼운 설치)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 의존성 파일 먼저 복사 → 레이어 캐시 활용
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# 소스 복사
COPY . .

EXPOSE 8000

# fastapi dev = uvicorn + --reload (watch와 조합)
CMD ["uv", "run", "fastapi", "dev", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
