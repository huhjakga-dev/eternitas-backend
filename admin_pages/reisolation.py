import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("재격리 관리")

tabs = st.tabs(["세션 목록", "세션 생성", "공격 판정", "승무원 전투", "탈출 처리"])

_, crews_data  = api("get", "/runners/crew")
_, cargos_data = api("get", "/runners/cargo")
_, sessions_data = api("get", "/reisolation/sessions")

crews_data    = crews_data    if isinstance(crews_data, list)    else []
cargos_data   = cargos_data   if isinstance(cargos_data, list)   else []
sessions_data = sessions_data if isinstance(sessions_data, list) else []

crew_map      = {c["crew_name"]: c["crew_id"]   for c in crews_data}
cargo_map     = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}
cargo_id_name = {c["cargo_id"]: c["cargo_name"] for c in cargos_data}
escaped_cargos = {c["cargo_name"]: c["cargo_id"] for c in cargos_data if c.get("is_escaped")}

active_sessions = [s for s in sessions_data if s["status"] == "active"]

def session_label(s):
    return f"{cargo_id_name.get(s['cargo_id'], s['cargo_id'][:8])} — {s['session_id'][:8]}… (HP {s['cargo_current_hp']}/{s['cargo_max_hp']})"

session_map = {session_label(s): s["session_id"] for s in active_sessions}

GRADE_WEIGHT = {"standard": 5, "non_standard": 15, "overload": 30, "fixed": 50}
GRADE_HP     = {"standard": 100, "non_standard": 230, "overload": 330, "fixed": 500}

# ── 세션 목록 ─────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("재격리 세션 목록 (최신 20개)")
    if st.button("조회", key="ri_list"):
        s, d = api("get", "/reisolation/sessions")
        if s == 200:
            import pandas as pd
            if d:
                rows = [{
                    "세션 ID": r["session_id"][:8] + "…",
                    "화물": cargo_id_name.get(r["cargo_id"], r["cargo_id"][:8]),
                    "상태": r["status"],
                    "화물 HP": f"{r['cargo_current_hp']}/{r['cargo_max_hp']}",
                    "참여 인원": len(r["crew_ids"]),
                } for r in d]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("세션 없음")
        else:
            st.error(d)

# ── 세션 생성 ─────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("재격리 세션 생성")

    if not escaped_cargos:
        st.info("탈출 상태인 화물이 없습니다. 탈출 처리 탭에서 먼저 탈출 처리 해주세요.")
    else:
        sel_cargo = st.selectbox("탈출한 화물", list(escaped_cargos.keys()), key="ri_cargo")
        sel_crews = st.multiselect("참여 승무원", list(crew_map.keys()), key="ri_crews")

        # 선택 화물 정보 표시
        cargo_detail = next((c for c in cargos_data if c["cargo_id"] == escaped_cargos[sel_cargo]), None)
        if cargo_detail:
            grade = cargo_detail.get("grade", "standard")
            threshold = int((cargo_detail.get("cause", 10) or 10) * 1.2) + GRADE_WEIGHT.get(grade, 5)
            st.info(f"등급: {grade} | 재격리 HP: {GRADE_HP.get(grade, 100)} | 명중 임계치: {threshold}")

        if st.button("세션 생성", key="btn_ri_create"):
            s, d = api("post", "/reisolation/sessions", json={
                "cargo_id": escaped_cargos[sel_cargo],
                "crew_ids": [crew_map[c] for c in sel_crews],
            })
            if s in (200, 201):
                st.success(d)
            else:
                st.error(d)

# ── 공격 판정 ─────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("공격 판정")

    if not session_map:
        st.info("진행 중인 재격리 세션 없음")
    else:
        sel_session = st.selectbox("세션 선택", list(session_map.keys()), key="ri_session")
        sel_crew    = st.selectbox("공격 승무원", list(crew_map.keys()), key="ri_atk_crew")

        if st.button("공격", key="btn_ri_attack"):
            sid = session_map[sel_session]
            s, d = api("post", f"/reisolation/sessions/{sid}/attack", json={
                "crew_id": crew_map[sel_crew],
            })
            if s == 200:
                success_str = "명중" if d["success"] else "실패"
                st.markdown(f"""
**{d['crew_name']}** (무기: {d['weapon'] or '없음'})
- 굴림: 1d{(next((c for c in crews_data if c["crew_id"] == crew_map[sel_crew]), {})).get("luckiness", "?") * 5 if False else "?"}({d['crew_roll']}) + {d['hit_bonus']} = **{d['final_roll']}** vs {d['threshold']} → **{success_str}**
- 피해: {d['damage_dealt']} | 화물 HP: {d['cargo_hp']}
- 반격: -{d['counter_damage']} ({d['damage_type']})
""")
                if d["counter_kills"]:
                    st.error(f"반격으로 사망: {', '.join(d['counter_kills'])}")
                if d["session_resolved"]:
                    result_label = "재격리 성공" if d["final_result"] == "success" else "재격리 실패 (전멸)"
                    st.success(f"세션 종료: {result_label}")
                    st.rerun()
            else:
                st.error(d)

# ── 승무원 vs 승무원 전투 ─────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("승무원 vs 승무원 전투")
    st.caption("행운 + 착용 무기 보정 대항. 높은 쪽이 승리 후 상대에게 무기 데미지 적용.")

    if len(crew_map) < 2:
        st.info("승무원 2명 이상 필요")
    else:
        names = list(crew_map.keys())
        ca1, ca2 = st.columns(2)
        crew_a = ca1.selectbox("승무원 A", names, key="cc_a")
        crew_b = ca2.selectbox("승무원 B", [n for n in names if n != crew_a], key="cc_b")

        if st.button("전투 판정", key="btn_cc"):
            s, d = api(
                "post", "/reisolation/crew-combat",
                params={"crew_a_id": crew_map[crew_a], "crew_b_id": crew_map[crew_b]},
            )
            if s == 200:
                st.markdown(f"""
**{d['crew_a']}** (무기: {d['weapon_a'] or '없음'}) — 굴림 **{d['roll_a']}**
vs
**{d['crew_b']}** (무기: {d['weapon_b'] or '없음'}) — 굴림 **{d['roll_b']}**

승리: **{d['winner']}** → **{d['loser']}**에게 **{d['damage']}** 피해
{d['loser']} 남은 HP: {d['loser_hp']}{"  |  사망" if d['loser_killed'] else ""}
""")
            else:
                st.error(d)

# ── 탈출 처리 ─────────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("화물 탈출 처리")
    st.caption("화물의 탈출 상태를 토글합니다. 탈출 상태여야 재격리 세션을 만들 수 있습니다.")

    if not cargo_map:
        st.info("등록된 화물 없음")
    else:
        sel_escape_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="escape_cargo")
        cargo_detail_e   = next((c for c in cargos_data if c["cargo_id"] == cargo_map[sel_escape_cargo]), None)

        if cargo_detail_e:
            is_esc = cargo_detail_e.get("is_escaped", False)
            st.info(f"현재 상태: {'탈출 중' if is_esc else '격리 중'}")

        if st.button("탈출 상태 토글", key="btn_escape_toggle"):
            s, d = api("patch", f"/runners/cargo/{cargo_map[sel_escape_cargo]}/escape")
            if s == 200:
                st.success(f"탈출 상태 → {d['is_escaped']}")
                st.rerun()
            else:
                st.error(d)
