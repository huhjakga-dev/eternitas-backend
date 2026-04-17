"""
ETERNITAS 관리 대시보드
실행: streamlit run admin_dashboard.py
"""
import os
import uuid
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


st.set_page_config(page_title="ETERNITAS 관리", page_icon="🛠", layout="wide")
st.image("eternitas_banner.png", use_container_width=True)
st.title("ETERNITAS — 관리 대시보드")

# tabs = st.tabs(["세션", "전조 선언", "승무원 대응", "본 작업", "러너 등록", "패턴 등록"])
tabs = st.tabs(["러너 등록"])


# ── 러너 등록 탭 ───────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("러너 등록")
    runner_type = st.radio("유형", ["승무원", "화물"], horizontal=True)

    if runner_type == "승무원":
        crew_name = st.text_input("이름", key="runner_crew_name")
        crew_type = st.radio("승무원 유형", ["자원", "사형수"], horizontal=True, key="runner_crew_type")
        crew_type_val = "volunteer" if crew_type == "자원" else "convict"

        c1, c2, c3, c4, c5 = st.columns(5)
        health      = c1.number_input("체력",   1, 10, 1, key="r_health")
        mentality   = c2.number_input("정신력", 1, 10, 1, key="r_mentality")
        strength    = c3.number_input("근력",   1, 10, 1, key="r_strength")
        inteligence = c4.number_input("지력",   1, 10, 1, key="r_int")
        luckiness   = c5.number_input("행운",   1, 10, 1, key="r_luck")
        total = health + mentality + strength + inteligence + luckiness
        st.caption(f"스탯 합계: {total} / 25")
        mech_lv = st.number_input("기계화 단계", 0, 4, 0, key="r_mech")

        if st.button("승무원 등록"):
            status, data = api("post", "/runners/crew", json={
                "band_user_id": str(uuid.uuid4()),
                "crew_name": crew_name,
                "crew_type": crew_type_val,
                "health": health, "mentality": mentality,
                "strength": strength, "inteligence": inteligence,
                "luckiness": luckiness, "mechanization_lv": mech_lv,
            })
            if status in (200, 201):
                st.success(data)
            else:
                st.error(data)

    else:
        cargo_code = st.text_input("화물 코드 (공개용)", key="runner_cargo_code")
        cargo_name = st.text_input("화물 이름 (관측 후 공개)", key="runner_cargo_name")
        grade = st.selectbox("위험 등급", [
            ("일반", "standard"),
            ("비규격", "non_standard"),
            ("과적", "overload"),
            ("고정", "fixed"),
        ], format_func=lambda x: x[0], key="runner_grade")

        c1, c2, c3, c4, c5 = st.columns(5)
        health      = c1.number_input("체력",   1, 10, 1, key="rc_health")
        mentality   = c2.number_input("정신력", 1, 10, 1, key="rc_mentality")
        strength    = c3.number_input("근력",   1, 10, 1, key="rc_strength")
        inteligence = c4.number_input("지력",   1, 10, 1, key="rc_int")
        cause       = c5.number_input("원인",   1, 10, 1, key="rc_cause")
        total = health + mentality + strength + inteligence + cause
        st.caption(f"스탯 합계: {total} / 25")

        if st.button("화물 등록"):
            status, data = api("post", "/runners/cargo", json={
                "band_user_id": str(uuid.uuid4()),
                "cargo_name": cargo_name,
                "cargo_code": cargo_code or None,
                "grade": grade[1],
                "health": health, "mentality": mentality,
                "strength": strength, "inteligence": inteligence,
                "cause": cause,
            })
            if status in (200, 201):
                st.success(data)
            else:
                st.error(data)


# ── 세션 탭 ────────────────────────────────────────────────────────────────────
# with tabs[0]:
#     st.subheader("작업 세션")
#     col_a, col_b = st.columns(2)
#     with col_a:
#         if st.button("세션 목록 조회"):
#             status, data = api("get", "/works/test/sessions")
#             if status == 200:
#                 st.dataframe(data)
#             else:
#                 st.error(data)
#     with col_b:
#         st.markdown("**새 세션 생성**")
#         cargo_id = st.text_input("cargo_id (UUID)", key="new_session_cargo_id")
#         post_key = st.text_input("post_key", value="manual_post_key", key="new_session_post_key")
#         crew_ids_raw = st.text_area("참여 승무원 UUID (줄바꿈 구분, 최대 3명)", key="new_session_crew_ids")
#         if st.button("세션 생성"):
#             crew_ids = [x.strip() for x in crew_ids_raw.strip().splitlines() if x.strip()]
#             status, data = api("post", "/works/test/sessions", json={
#                 "cargo_id": cargo_id, "post_key": post_key, "crew_ids": crew_ids,
#             })
#             if status in (200, 201):
#                 st.success(data)
#             else:
#                 st.error(data)


# ── 전조 선언 탭 ───────────────────────────────────────────────────────────────
# with tabs[1]:
#     st.subheader("전조 선언 처리")
#     session_id = st.text_input("session_id (UUID)", key="pre_session_id")
#     content = st.text_input("댓글 내용 (예: [선언])", value="[선언]", key="pre_content")
#     crew_id = st.text_input("crew_id (UUID, 선택)", key="pre_crew_id")
#     if st.button("전조 선언 실행"):
#         body = {"content": content, "comment_key": "manual_pre_comment"}
#         if crew_id:
#             body["crew_id"] = crew_id
#         status, data = api("post", f"/works/test/precursor-declaration/{session_id}", json=body)
#         if status == 200:
#             st.success(data)
#         else:
#             st.error(data)


# ── 승무원 대응 탭 ─────────────────────────────────────────────────────────────
# with tabs[2]:
#     st.subheader("승무원 대응 처리")
#     session_id = st.text_input("session_id (UUID)", key="resp_session_id")
#     content = st.text_area("대응 댓글 내용", key="resp_content")
#     crew_id = st.text_input("crew_id (UUID)", key="resp_crew_id")
#     if st.button("대응 처리 실행"):
#         status, data = api("post", f"/works/test/crew-response/{session_id}", json={
#             "content": content, "comment_key": "manual_resp_comment", "crew_id": crew_id,
#         })
#         if status == 200:
#             st.success(data)
#         else:
#             st.error(data)


# ── 본 작업 탭 ─────────────────────────────────────────────────────────────────
# with tabs[3]:
#     st.subheader("본 작업 처리")
#     session_id = st.text_input("session_id (UUID)", key="work_session_id")
#     content = st.text_input("작업 명령 (예: 체력 5회 지력 3회)", key="work_content")
#     crew_id = st.text_input("crew_id (UUID)", key="work_crew_id")
#     if st.button("작업 실행"):
#         status, data = api("post", f"/works/test/main-work/{session_id}", json={
#             "content": content, "comment_key": "manual_work_comment", "crew_id": crew_id,
#         })
#         if status == 200:
#             st.success(data)
#         else:
#             st.error(data)


# ── 패턴 등록 탭 ───────────────────────────────────────────────────────────────
# with tabs[5]:
#     st.subheader("화물 전조 패턴 등록")
#     cargo_id = st.text_input("cargo_id (UUID)", key="pattern_cargo_id")
#     pattern_name = st.text_input("패턴 이름", key="pattern_name")
#     description = st.text_area("전조 현상 설명 (밴드에 게시될 내용)", key="pattern_desc")
#     answer = st.text_area("정답 대응 (LLM 판정 기준)", key="pattern_answer")
#     st.markdown("**버프 (성공 시)**")
#     bc1, bc2, bc3 = st.columns(3)
#     buff_str  = bc1.number_input("근력 버프", value=0.0, step=0.1, key="buff_str")
#     buff_int  = bc2.number_input("지력 버프", value=0.0, step=0.1, key="buff_int")
#     buff_luck = bc3.number_input("행운 버프", value=0.0, step=0.1, key="buff_luck")
#     buff_dmg_red = st.number_input("데미지 감소율 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="buff_dmg_red")
#     st.markdown("**디버프 (실패 시)**")
#     dc1, dc2, dc3 = st.columns(3)
#     debuff_str  = dc1.number_input("근력 디버프", value=0.0, step=0.1, key="debuff_str")
#     debuff_int  = dc2.number_input("지력 디버프", value=0.0, step=0.1, key="debuff_int")
#     debuff_luck = dc3.number_input("행운 디버프", value=0.0, step=0.1, key="debuff_luck")
#     debuff_dmg_inc = st.number_input("데미지 증가율 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="debuff_dmg_inc")
#     instant_kill = st.number_input("대실패 즉사 확률 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="instant_kill")
#     if st.button("패턴 등록/수정"):
#         status, data = api("post", "/runners/cargo/pattern", json={
#             "cargo_id": cargo_id, "pattern_name": pattern_name,
#             "description": description, "answer": answer,
#             "buff_stat_json": {"strength": buff_str, "inteligence": buff_int, "luckiness": buff_luck, "health": 0.0, "mentality": 0.0},
#             "buff_damage_reduction": buff_dmg_red,
#             "debuff_stat_json": {"strength": debuff_str, "inteligence": debuff_int, "luckiness": debuff_luck, "health": 0.0, "mentality": 0.0},
#             "debuff_demage_increase": debuff_dmg_inc,
#             "instant_kill_rate": instant_kill if instant_kill > 0 else None,
#         })
#         if status in (200, 201):
#             st.success(data)
#         else:
#             st.error(data)
