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

# 공통 데이터 로드
_, crews_data   = api("get", "/runners/crew")
_, cargos_data  = api("get", "/runners/cargo")
_, sessions_data = api("get", "/works/sessions")

crews_data   = crews_data   if isinstance(crews_data, list)   else []
cargos_data  = cargos_data  if isinstance(cargos_data, list)  else []
sessions_data = sessions_data if isinstance(sessions_data, list) else []

crew_map    = {f"{c['crew_name']}": c["crew_id"]   for c in crews_data}
cargo_map   = {f"{c['cargo_name']}": c["cargo_id"] for c in cargos_data}
cargo_id_to_name = {c["cargo_id"]: c["cargo_name"] for c in cargos_data}

def session_label(s):
    cargo_name = cargo_id_to_name.get(s["cargo_id"], s["cargo_id"][:8])
    return f"[{s['status']}] {cargo_name} — {s['id'][:8]}…"

active_sessions = [s for s in sessions_data if s["status"] != "resolved"]
session_map = {session_label(s): s["id"] for s in active_sessions}

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

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        sel_cargo  = st.selectbox("화물 선택", list(cargo_map.keys()), key="new_cargo")
        sel_crews  = st.multiselect("참여 승무원 (최대 3명)", list(crew_map.keys()), max_selections=3, key="new_crews")

        if st.button("세션 생성"):
            status, data = api("post", "/works/sessions", json={
                "cargo_id": cargo_map[sel_cargo],
                "crew_ids": [crew_map[c] for c in sel_crews],
            })
            if status in (200, 201):
                st.success(data)
            else:
                st.error(data)

# ── 전조 진행 ─────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("전조 진행")

    if not session_map:
        st.info("진행 중인 세션 없음")
    else:
        pre_session_label = st.selectbox("세션 선택", list(session_map.keys()), key="pre_session")
        pre_sid           = session_map[pre_session_label]
        pre_session       = next(s for s in sessions_data if s["id"] == pre_sid)

        # 선택된 세션의 화물에 달린 패턴 로드
        _, patterns_data = api("get", f"/runners/cargo/{pre_session['cargo_id']}/patterns")
        patterns_data = patterns_data if isinstance(patterns_data, list) else []
        pattern_map   = {f"{p['pattern_name']}": p["pattern_id"] for p in patterns_data}

        if not pattern_map:
            st.warning("해당 화물에 등록된 패턴 없음")
        else:
            pre_pattern_label = st.selectbox("패턴 선택", list(pattern_map.keys()), key="pre_pattern")
            pre_crew_label    = st.selectbox("판정 승무원", list(crew_map.keys()), key="pre_crew")
            pre_stat          = st.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="pre_stat")
            pre_success       = st.radio("승무원 성공 여부", ["성공", "실패"], horizontal=True, key="pre_success")

            if st.button("전조 판정"):
                status, data = api("post", f"/works/sessions/{pre_sid}/precursor-calculate", json={
                    "pattern_id": pattern_map[pre_pattern_label],
                    "crew_id":    crew_map[pre_crew_label],
                    "stat":       STAT_OPTIONS[pre_stat],
                    "is_success": pre_success == "성공",
                })
                if status == 200:
                    st.success(data)
                else:
                    st.error(data)

# ── 본 작업 ──────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("본 작업")

    if not session_map:
        st.info("진행 중인 세션 없음")
    else:
        work_session_label = st.selectbox("세션 선택", list(session_map.keys()), key="work_session")
        work_sid           = session_map[work_session_label]
        work_crew_label    = st.selectbox("작업 승무원", list(crew_map.keys()), key="work_crew")

        n = st.number_input("명령 수", 1, 5, 1, key="work_n")
        commands = []
        for i in range(int(n)):
            c1, c2 = st.columns([3, 1])
            stat  = c1.selectbox(f"스탯 {i+1}", list(STAT_OPTIONS.keys()), key=f"ws_{i}")
            count = c2.number_input("횟수", 1, 20, 1, key=f"wc_{i}")
            commands.append({"stat": STAT_OPTIONS[stat], "count": int(count)})

        if st.button("작업 실행"):
            status, data = api("post", f"/works/sessions/{work_sid}/main-work", json={
                "crew_id":  crew_map[work_crew_label],
                "commands": commands,
            })
            if status == 200:
                st.success(data)
            else:
                st.error(data)
