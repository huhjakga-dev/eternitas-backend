import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    BAND_BASE_URL: str = os.getenv("BAND_BASE_URL", "https://openapi.band.us/v2/band")
    BAND_ACCESS_TOKEN: str = os.getenv("BAND_ACCESS_TOKEN", "")
    BAND_KEY: str = os.getenv("BAND_KEY", "")


settings = Settings()
