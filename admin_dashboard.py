"""
ETERNITAS 관리 대시보드
실행: streamlit run admin_dashboard.py
"""
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("ADMIN_API_BASE", "http://localhost:8000")


def api(method: str, path: str, **kwargs):
    try:
        resp = getattr(requests, method)(f"{API_BASE}{path}", timeout=30, **kwargs)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, {"error": str(e)}


import pathlib
_here = pathlib.Path(__file__).parent

pg = st.navigation([
    st.Page(str(_here / "admin_pages" / "runners.py"), title="러너 등록",  icon=":material/person_add:"),
    st.Page(str(_here / "admin_pages" / "patterns.py"), title="패턴 등록", icon=":material/pattern:"),
    st.Page(str(_here / "admin_pages" / "works.py"),   title="작업 관리", icon=":material/build:"),
])
pg.run()
