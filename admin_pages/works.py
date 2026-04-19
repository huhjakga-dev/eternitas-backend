import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("작업 관리")

tabs = st.tabs(["세션 목록", "세션 생성", "전조 진행", "본 작업"])

STAT_OPTIONS = {
    "체력":   "health",
    "정신력": "mentality",
    "근력":   "strength",
    "지력":   "inteligence",
    "행운":   "luckiness",
}

# ── 세션 목록 ─────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("세션 목록 (최근 20개)")
    if st.button("조회"):
        status, data = api("get", "/works/sessions")
        if status == 200:
            import pandas as pd
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True) if data else st.info("세션 없음")
        else:
            st.error(data)

# ── 세션 생성 ─────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("세션 생성")
    cargo_id  = st.text_input("cargo_id (UUID)", key="new_cargo_id")
    crew_raw  = st.text_area("참여 승무원 UUID (줄바꿈 구분, 최대 3명)", key="new_crew_ids")

    if st.button("세션 생성"):
        crew_ids = [x.strip() for x in crew_raw.strip().splitlines() if x.strip()]
        status, data = api("post", "/works/sessions", json={"cargo_id": cargo_id, "crew_ids": crew_ids})
        st.success(data) if status in (200, 201) else st.error(data)

# ── 전조 진행 ─────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("전조 진행")
    pre_sid        = st.text_input("session_id (UUID)", key="pre_sid")
    pre_pattern_id = st.text_input("pattern_id (UUID)", key="pre_pattern_id")
    pre_crew_id    = st.text_input("crew_id (UUID)", key="pre_crew_id")
    pre_stat       = st.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="pre_stat")
    pre_success    = st.radio("승무원 성공 여부", ["성공", "실패"], horizontal=True, key="pre_success")

    if st.button("전조 판정"):
        status, data = api("post", f"/works/sessions/{pre_sid}/precursor-calculate", json={
            "pattern_id": pre_pattern_id,
            "crew_id":    pre_crew_id,
            "stat":       STAT_OPTIONS[pre_stat],
            "is_success": pre_success == "성공",
        })
        st.success(data) if status == 200 else st.error(data)

# ── 본 작업 ──────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("본 작업")
    work_sid     = st.text_input("session_id (UUID)", key="work_sid")
    work_crew_id = st.text_input("crew_id (UUID)", key="work_crew")

    n = st.number_input("명령 수", 1, 5, 1, key="work_n")
    commands = []
    for i in range(int(n)):
        c1, c2 = st.columns([3, 1])
        stat  = c1.selectbox(f"스탯 {i+1}", list(STAT_OPTIONS.keys()), key=f"ws_{i}")
        count = c2.number_input("횟수", 1, 20, 1, key=f"wc_{i}")
        commands.append({"stat": STAT_OPTIONS[stat], "count": int(count)})

    if st.button("작업 실행"):
        status, data = api("post", f"/works/sessions/{work_sid}/main-work", json={
            "crew_id":  work_crew_id,
            "commands": commands,
        })
        st.success(data) if status == 200 else st.error(data)
