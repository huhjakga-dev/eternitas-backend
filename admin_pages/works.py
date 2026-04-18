import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("작업 관리")

tabs = st.tabs(["세션 목록", "세션 생성", "전조 선언", "승무원 대응", "본 작업"])

STAT_OPTIONS = {
    "체력":   "health",
    "정신력": "mentality",
    "근력":   "strength",
    "지력":   "inteligence",
    "행운":   "luckiness",
}

RESULT_OPTIONS = {
    "성공":   "success",
    "무효":   "invalid",
    "실패":   "fail",
    "대실패": "critical_fail",
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
    post_key  = st.text_input("post_key", value="manual_post_key", key="new_post_key")
    crew_raw  = st.text_area("참여 승무원 UUID (줄바꿈 구분, 최대 3명)", key="new_crew_ids")

    if st.button("세션 생성"):
        crew_ids = [x.strip() for x in crew_raw.strip().splitlines() if x.strip()]
        status, data = api("post", "/works/sessions", json={"cargo_id": cargo_id, "post_key": post_key, "crew_ids": crew_ids})
        st.success(data) if status in (200, 201) else st.error(data)

# ── 전조 선언 ─────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("전조 선언")
    pre_sid = st.text_input("session_id (UUID)", key="pre_sid")

    if st.button("전조 선언 처리"):
        status, data = api("post", f"/works/sessions/{pre_sid}/precursor-declaration")
        st.success(data) if status == 200 else st.error(data)

# ── 승무원 대응 ───────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("승무원 대응")
    resp_sid     = st.text_input("session_id (UUID)", key="resp_sid")
    resp_crew_id = st.text_input("crew_id (UUID)", key="resp_crew")
    resp_result  = st.radio("판정 결과", list(RESULT_OPTIONS.keys()), horizontal=True, key="resp_result")

    if st.button("대응 처리"):
        status, data = api("post", f"/works/sessions/{resp_sid}/crew-response", json={
            "crew_id": resp_crew_id,
            "result":  RESULT_OPTIONS[resp_result],
        })
        st.success(data) if status == 200 else st.error(data)

# ── 본 작업 ──────────────────────────────────────────────────────────────────
with tabs[4]:
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
