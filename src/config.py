import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    BAND_BASE_URL: str = os.getenv("BAND_BASE_URL", "https://openapi.band.us/v2/band")
    BAND_ACCESS_TOKEN: str = os.getenv("BAND_ACCESS_TOKEN", "")
    BAND_KEY: str = os.getenv("BAND_KEY", "")
    # Ollama: Docker 컨테이너 → 호스트 머신 접근
    OLLAMA_BASE_URL: str = os.getenv(
        "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
    )
    # ollama create eternitas-llm -f Modelfile 로 생성한 모델명
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "eternitas")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()
