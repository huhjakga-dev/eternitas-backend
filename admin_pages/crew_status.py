import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("승무원 상태 관리")

tabs = st.tabs(["상태 변경", "상태이상 등록", "상태이상 적용"])

_, crews_data  = api("get", "/runners/crew")
_, cargos_data = api("get", "/runners/cargo")
crews_data  = crews_data  if isinstance(crews_data,  list) else []
cargos_data = cargos_data if isinstance(cargos_data, list) else []
crew_map  = {c["crew_name"]:  c["crew_id"]  for c in crews_data}
cargo_map = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}

_, se_data = api("get", "/runners/status-effects")
se_data = se_data if isinstance(se_data, list) else []
se_map = {se["name"]: se["status_effect_id"] for se in se_data}

# ── 상태 변경 ─────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("즉사 / HP·SP 직접 조정")

    if not crew_map:
        st.info("등록된 승무원 없음")
    else:
        sel = st.selectbox("승무원 선택", list(crew_map.keys()), key="cs_crew")
        cid = crew_map[sel]

        st.markdown("**즉사 처리**")
        if st.button("즉사 처리", type="primary", key="btn_kill"):
            s, d = api("post", f"/runners/crew/{cid}/kill")
            if s == 200:
                st.success(f"{sel} 즉사 처리 완료")
            else:
                st.error(d)

        st.divider()
        st.markdown("**HP / SP 직접 조정** (양수=회복, 음수=피해)")
        c1, c2 = st.columns(2)
        hp_delta = c1.number_input("HP 변화량", value=0, step=1, key="cs_hp")
        sp_delta = c2.number_input("SP 변화량", value=0, step=1, key="cs_sp")
        note = st.text_input("메모 (선택)", key="cs_note")

        if st.button("적용", key="btn_hpsp"):
            s, d = api("patch", f"/runners/crew/{cid}/hp-sp", json={
                "hp_delta": int(hp_delta),
                "sp_delta": int(sp_delta),
                "note": note or None,
            })
            if s == 200:
                st.success(f"HP {d['hp']}/{d['max_hp']} / SP {d['sp']}/{d['max_sp']}")
            else:
                st.error(d)

# ── 상태이상 등록 ─────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("상태이상 등록")

    se_name = st.text_input("상태이상 이름", key="se_name")
    se_desc = st.text_input("설명 (선택)", key="se_desc")

    st.markdown("**스탯 영향** (양수=버프, 음수=디버프)")
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    se_hp   = sc1.number_input("체력",   value=0.0, step=0.1, key="se_hp")
    se_sp   = sc2.number_input("정신력", value=0.0, step=0.1, key="se_sp")
    se_str  = sc3.number_input("근력",   value=0.0, step=0.1, key="se_str")
    se_int  = sc4.number_input("지력",   value=0.0, step=0.1, key="se_int")
    se_luck = sc5.number_input("행운",   value=0.0, step=0.1, key="se_luck")

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
        st.stop()

    se_cargo_label = st.selectbox("참조 화물", list(cargo_map.keys()), key="se_cargo",
                                   help="해당 화물이 격리될 때 이 상태이상이 자동 해제됩니다.")
    se_cargo_id = cargo_map[se_cargo_label]

    st.markdown("**주기 데미지** (선택)")
    se_use_tick = st.checkbox("주기 데미지 사용", key="se_use_tick")
    se_tick_dmg = None
    se_tick_int = None
    if se_use_tick:
        tc1, tc2 = st.columns(2)
        se_tick_dmg = tc1.number_input("틱당 데미지", min_value=1, value=3, key="se_tick_dmg")
        se_tick_int = tc2.number_input("주기 (분)", min_value=1, value=10, key="se_tick_int")
        st.caption(f"→ {se_tick_int}분마다 화물 피해 유형으로 {se_tick_dmg} 데미지")

    st.markdown("**만료 조건** (선택 — 둘 다 설정 시 먼저 도달한 조건으로 해제)")
    ex1, ex2 = st.columns(2)
    se_duration = ex1.number_input("지속 시간 (분, 0=무제한)", min_value=0, value=0, key="se_duration")
    se_max_ticks = ex2.number_input("최대 틱 횟수 (0=무제한)", min_value=0, value=0, key="se_max_ticks")
    if se_duration or se_max_ticks:
        parts = []
        if se_duration:
            parts.append(f"{se_duration}분 경과")
        if se_max_ticks:
            parts.append(f"틱 {se_max_ticks}회 도달")
        st.caption(f"→ {' 또는 '.join(parts)} 시 자동 해제 (또는 화물 격리 시 해제)")

    if st.button("상태이상 등록", key="btn_se_reg"):
        if not se_name.strip():
            st.error("상태이상 이름을 입력해주세요.")
        else:
            s, d = api("post", "/runners/status-effects", json={
                "name":        se_name.strip(),
                "cargo_id":    se_cargo_id,
                "description": se_desc or None,
                "stat_json": {
                    "health": se_hp, "mentality": se_sp, "strength": se_str,
                    "inteligence": se_int, "luckiness": se_luck,
                },
                "tick_damage":           int(se_tick_dmg) if se_use_tick and se_tick_dmg else None,
                "tick_interval_minutes": int(se_tick_int) if se_use_tick and se_tick_int else None,
                "duration_minutes":      int(se_duration)  if se_duration  else None,
                "max_ticks":             int(se_max_ticks) if se_max_ticks else None,
            })
            if s in (200, 201):
                st.success(d)
            else:
                st.error(d)

# ── 상태이상 적용 / 해제 ──────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("상태이상 적용 / 해제")

    if not crew_map:
        st.info("등록된 승무원 없음")
    elif not se_map:
        st.info("등록된 상태이상 없음")
    else:
        sel2 = st.selectbox("승무원 선택", list(crew_map.keys()), key="se_crew")
        cid2 = crew_map[sel2]

        # 현재 적용 중인 상태이상
        st.markdown("**현재 적용 중인 상태이상**")
        cs2, cd2 = api("get", f"/runners/crew/{cid2}/status-effects")
        if cs2 == 200 and cd2:
            for item in cd2:
                col_name, col_info, col_rm = st.columns([3, 4, 1])
                col_name.write(f"**{item['name']}**")
                info_parts = []
                if item.get("expires_at"):
                    info_parts.append(f"만료: {item['expires_at'][:16]}")
                if item.get("max_ticks"):
                    info_parts.append(f"틱 {item.get('tick_count', 0)}/{item['max_ticks']}")
                if item.get("tick_interval_minutes"):
                    info_parts.append(f"{item['tick_interval_minutes']}분 주기")
                col_info.caption("  |  ".join(info_parts) if info_parts else (item.get("note") or "화물 격리 시 해제"))
                if col_rm.button("해제", key=f"rm_se_{item['crew_status_effect_id']}"):
                    rs, rd = api("delete", f"/runners/crew/{cid2}/status-effect/{item['crew_status_effect_id']}")
                    if rs == 200:
                        st.rerun()
                    else:
                        st.error(rd)
        else:
            st.caption("적용된 상태이상 없음")

        st.divider()

        sel_se = st.selectbox("적용할 상태이상", list(se_map.keys()), key="se_sel")
        apply_note = st.text_input("메모 (선택)", key="se_apply_note")
        if st.button("상태이상 적용", key="btn_se_apply"):
            ps, pd_ = api(
                "post",
                f"/runners/crew/{cid2}/status-effect",
                params={"status_effect_id": se_map[sel_se], "note": apply_note or None},
            )
            if ps in (200, 201):
                st.success(pd_)
                st.rerun()
            else:
                st.error(pd_)
