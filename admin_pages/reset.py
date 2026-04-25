import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("데이터 초기화")

_, crews_data  = api("get", "/runners/crew")
_, cargos_data = api("get", "/runners/cargo")
crews_data  = crews_data  if isinstance(crews_data,  list) else []
cargos_data = cargos_data if isinstance(cargos_data, list) else []

crew_map  = {c["crew_name"]:  c["crew_id"]  for c in crews_data}
cargo_map = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}

tabs = st.tabs(["전체 초기화", "승무원 개별 초기화", "화물 개별 초기화"])

# ── 전체 초기화 ───────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("전체 초기화")
    st.warning(
        "모든 작업·재격리 세션과 로그가 삭제됩니다.\n\n"
        "승무원 HP·SP·사망 상태와 화물 집계(성공/실패/관측률/탈출 여부)가 초기값으로 돌아갑니다.",
        icon="⚠️",
    )

    confirm = st.checkbox("위 내용을 확인했으며 초기화를 진행합니다.", key="confirm_all")
    if st.button("전체 초기화 실행", type="primary", disabled=not confirm, key="btn_reset_all"):
        s, d = api("post", "/admin/reset/sessions")
        if s == 200:
            st.success(
                f"초기화 완료 — 승무원 {d['crews_reset']}명 / 화물 {d['cargos_reset']}개 복원"
            )
            st.rerun()
        else:
            st.error(d)

# ── 승무원 개별 초기화 ────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("승무원 개별 초기화")
    st.caption("선택한 승무원의 HP·SP·사망 상태와 적용된 상태이상을 초기화합니다.")

    if not crew_map:
        st.info("등록된 승무원 없음")
    else:
        sel_crew = st.selectbox("승무원 선택", list(crew_map.keys()), key="rc_crew")
        crew_info = next((c for c in crews_data if c["crew_id"] == crew_map[sel_crew]), {})
        st.caption(
            f"현재 HP {crew_info.get('hp', '?')}  |  "
            f"사망: {'예' if crew_info.get('is_dead') else '아니오'}"
        )
        if st.button("승무원 초기화", key="btn_reset_crew"):
            s, d = api("post", f"/admin/reset/crew/{crew_map[sel_crew]}")
            if s == 200:
                st.success(f"{d['crew_name']} 초기화 완료 — HP {d['hp']} / SP {d['sp']}")
                st.rerun()
            else:
                st.error(d)

# ── 화물 개별 초기화 ──────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("화물 개별 초기화")
    st.caption("선택한 화물의 성공/실패 횟수·관측률·탈출 여부를 초기화합니다.")

    if not cargo_map:
        st.info("등록된 화물 없음")
    else:
        sel_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="rc_cargo")
        cargo_info = next((c for c in cargos_data if c["cargo_id"] == cargo_map[sel_cargo]), {})
        st.caption(
            f"성공 {cargo_info.get('success_count', 0)}회 / 실패 {cargo_info.get('failure_count', 0)}회 / "
            f"관측률 {cargo_info.get('observation_rate', 0):.0f}% / "
            f"탈출: {'예' if cargo_info.get('is_escaped') else '아니오'}"
        )
        if st.button("화물 초기화", key="btn_reset_cargo"):
            s, d = api("post", f"/admin/reset/cargo/{cargo_map[sel_cargo]}")
            if s == 200:
                st.success(f"{d['cargo_name']} 초기화 완료")
                st.rerun()
            else:
                st.error(d)
