import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("장비 관리")

tabs = st.tabs(["장비 목록", "장비 등록", "장비 할당"])

TYPE_OPTIONS = {"무기": "weapon", "방어구": "armor"}

# ── 장비 목록 ─────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("장비 목록")
    if st.button("조회"):
        status, data = api("get", "/runners/equipment")
        if status == 200:
            import pandas as pd
            rows = [
                {
                    "이름":         e["name"],
                    "유형":         "무기" if e["type"] == "weapon" else "방어구",
                    "기본 장비":    "O" if e["is_default"] else "",
                    "설명":         e.get("description") or "—",
                    "체력":         e["effects"].get("health", 0),
                    "정신력":       e["effects"].get("mentality", 0),
                    "근력":         e["effects"].get("strength", 0),
                    "지력":         e["effects"].get("inteligence", 0),
                    "행운":         e["effects"].get("luckiness", 0),
                    "equipment_id": e["equipment_id"],
                }
                for e in data
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True) if rows else st.info("등록된 장비 없음")
        else:
            st.error(data)

# ── 장비 등록 ─────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("장비 등록")
    eq_name    = st.text_input("장비 이름", key="eq_name")
    eq_type    = st.radio("장비 유형", list(TYPE_OPTIONS.keys()), horizontal=True, key="eq_type")
    eq_desc    = st.text_input("설명 (선택)", key="eq_desc")
    eq_default = st.checkbox("기본 장비 (전조 시 미착용 패널티 적용)", key="eq_default")

    st.markdown("**스탯 보정**")
    c1, c2, c3, c4, c5 = st.columns(5)
    eff_hp   = c1.number_input("체력",   value=0.0, step=0.1, key="eff_hp")
    eff_sp   = c2.number_input("정신력", value=0.0, step=0.1, key="eff_sp")
    eff_str  = c3.number_input("근력",   value=0.0, step=0.1, key="eff_str")
    eff_int  = c4.number_input("지력",   value=0.0, step=0.1, key="eff_int")
    eff_luck = c5.number_input("행운",   value=0.0, step=0.1, key="eff_luck")

    if TYPE_OPTIONS[eq_type] == "weapon":
        st.markdown("**전투 스탯 (무기 전용)**")
        wc1, wc2, wc3, wc4 = st.columns(4)
        hit_bonus  = wc1.number_input("명중 보정",       value=0,  step=1, key="eff_hit")
        damage_min = wc2.number_input("데미지 최솟값",   value=0,  step=1, key="eff_dmin")
        damage_max = wc3.number_input("데미지 최댓값",   value=0,  step=1, key="eff_dmax")
        min_roll   = wc4.number_input("굴림 최솟값 (0=없음)", value=0, step=1, key="eff_minroll")
    else:
        hit_bonus = damage_min = damage_max = min_roll = 0

    if st.button("장비 등록"):
        status, data = api("post", "/runners/equipment", json={
            "name":           eq_name,
            "equipment_type": TYPE_OPTIONS[eq_type],
            "description":    eq_desc or None,
            "is_default":     eq_default,
            "effects": {
                "health":      eff_hp,
                "mentality":   eff_sp,
                "strength":    eff_str,
                "inteligence": eff_int,
                "luckiness":   eff_luck,
                "hit_bonus":   int(hit_bonus),
                "damage_min":  int(damage_min),
                "damage_max":  int(damage_max),
                "min_roll":    int(min_roll),
            },
        })
        if status in (200, 201):
            st.success(data)
        else:
            st.error(data)

# ── 장비 할당 ─────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("장비 할당")

    # 승무원·장비 목록 로드
    s1, d1 = api("get", "/runners/crew")
    s2, d2 = api("get", "/runners/equipment")

    if s1 != 200 or s2 != 200:
        st.error("승무원 또는 장비 목록 로드 실패")
    else:
        crew_map = {f"{c['crew_name']} ({c['crew_id'][:8]}…)": c["crew_id"] for c in d1}
        eq_map   = {e["name"]: e["equipment_id"] for e in d2}

        if not crew_map:
            st.info("등록된 승무원 없음")
        elif not eq_map:
            st.info("등록된 장비 없음")
        else:
            selected_crew_label = st.selectbox("승무원 선택", list(crew_map.keys()), key="assign_crew")
            selected_crew_id    = crew_map[selected_crew_label]

            # 현재 보유 장비
            st.markdown("**현재 보유 장비**")
            cs, cd = api("get", f"/runners/crew/{selected_crew_id}/equipment")
            if cs == 200:
                if cd:
                    for item in cd:
                        col_name, col_status, col_toggle, col_remove = st.columns([3, 1, 1, 1])
                        col_name.write(item["name"])
                        col_status.write("착용 중" if item["is_equipped"] else "미착용")
                        if col_toggle.button("토글", key=f"toggle_{item['equipment_id']}"):
                            ts, td = api("patch", f"/runners/crew/{selected_crew_id}/equipment/{item['equipment_id']}")
                            if ts == 200:
                                st.rerun()
                            else:
                                st.error(td)
                        if col_remove.button("회수", key=f"remove_{item['equipment_id']}"):
                            rs, rd = api("delete", f"/runners/crew/{selected_crew_id}/equipment/{item['equipment_id']}")
                            if rs == 200:
                                st.rerun()
                            else:
                                st.error(rd)
                else:
                    st.caption("보유 장비 없음")
            else:
                st.error(cd)

            st.divider()

            # 장비 할당
            owned_ids     = {item["equipment_id"] for item in (cd if cs == 200 else [])}
            available_eqs = {name: eid for name, eid in eq_map.items() if eid not in owned_ids}

            if available_eqs:
                selected_eq_label = st.selectbox("할당할 장비", list(available_eqs.keys()), key="assign_eq")
                if st.button("장비 할당"):
                    ps, pd_ = api(
                        "post",
                        f"/runners/crew/{selected_crew_id}/equipment",
                        params={"equipment_id": available_eqs[selected_eq_label]},
                    )
                    if ps in (200, 201):
                        st.success(pd_)
                        st.rerun()
                    else:
                        st.error(pd_)
            else:
                st.caption("할당 가능한 장비 없음 (모두 보유 중)")
