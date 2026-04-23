"""
ETERNITAS 러너 접수 현황 대시보드
실행: streamlit run registration_dashboard.py
"""
import os
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

HOST     = os.getenv("host")
PORT     = os.getenv("port", "5432")
USER     = os.getenv("user")
PASSWORD = os.getenv("password")
DBNAME   = os.getenv("dbname")

DATABASE_URL = (
    f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
)

GRADE_LABEL = {
    "standard":     "규격",
    "non_standard": "비규격",
    "overload":     "과적",
    "fixed":        "고착",
}

MECH = {0: "Lv.0", 1: "Lv.1", 2: "Lv.2", 3: "Lv.3", 4: "Lv.4"}


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

def get_db():
    return sessionmaker(bind=get_engine())()


def fetch_crews(db):
    return db.execute(text("""
        SELECT
            c.crew_name,
            c.crew_type,
            c.health, c.mentality, c.strength, c.inteligence, c.luckiness,
            c.mechanization_lv
        FROM crews c
        ORDER BY c.crew_type, c.crew_name
    """)).fetchall()


def fetch_cargos(db):
    return db.execute(text("""
        SELECT
            c.cargo_name,
            c.cargo_code,
            c.grade
        FROM cargos c
        ORDER BY c.grade, c.cargo_name
    """)).fetchall()


CREW_TYPE_LABEL = {
    "volunteer": "자원",
    "convict":   "사형수",
}


# ── 멀티페이지 진입점 ──────────────────────────────────────────────────────────

import pathlib
_here = pathlib.Path(__file__).parent

pg = st.navigation([
    st.Page(str(_here / "pages" / "home.py"),  title="전체 현황", icon=":material/dashboard:", default=True),
    st.Page(str(_here / "pages" / "crew.py"),  title="승무원",    icon=":material/person:"),
    st.Page(str(_here / "pages" / "cargo.py"), title="화물",      icon=":material/inventory_2:"),
])
pg.run()
