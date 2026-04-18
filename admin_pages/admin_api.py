import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("ADMIN_API_BASE", "http://localhost:8000")


def api(method: str, path: str, **kwargs):
    try:
        resp = getattr(requests, method)(f"{API_BASE}{path}", timeout=30, **kwargs)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, {"error": str(e)}
