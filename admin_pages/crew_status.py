import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("승무원 상태 관리")

tabs = st.tabs(["상태 변경", "상태이상 적용", "주사위 판정"])

_, crews_data = api("get", "/runners/crew")
crews_data = crews_data if isinstance(crews_data, list) else []
crew_map   = {c["crew_name"]: c["crew_id"] for c in crews_data}

_, se_data = api("get", "/runners/status-effects")
se_data = se_data if isinstance(se_data, list) else []
se_map  = {se["name"]: se["status_effect_id"] for se in se_data}

_STAT_KO     = {"health": "체력", "mentality": "정신력", "strength": "근력", "inteligence": "지력", "luckiness": "행운"}
STAT_OPTIONS = {v: k for k, v in _STAT_KO.items()}

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
        st.markdown("**토큰 지급 / 차감**")
        tc1, tc2 = st.columns([2, 1])
        token_delta = tc1.number_input("토큰 변화량 (양수=지급, 음수=차감)", value=0, step=1, key="cs_token")
        if tc2.button("적용", key="btn_token"):
            s, d = api("patch", f"/runners/crew/{cid}/token", params={"delta": int(token_delta)})
            if s == 200:
                st.success(f"{d['crew_name']} 토큰: {d['token']}")
            else:
                st.error(d)

        st.divider()
        st.markdown("**HP / SP 직접 조정** (양수=회복, 음수=피해)")
        c1, c2 = st.columns(2)
        hp_delta = c1.number_input("HP 변화량", value=0, step=1, key="cs_hp")
        sp_delta = c2.number_input("SP 변화량", value=0, step=1, key="cs_sp")
        note     = st.text_input("메모 (선택)", key="cs_note")

        if st.button("적용", key="btn_hpsp"):
            s, d = api("patch", f"/runners/crew/{cid}/hp-sp", json={
                "hp_delta": int(hp_delta),
                "sp_delta": int(sp_delta),
                "note":     note or None,
            })
            if s == 200:
                st.success(f"HP {d['hp']}/{d['max_hp']} / SP {d['sp']}/{d['max_sp']}")
            else:
                st.error(d)

# ── 상태이상 적용 / 해제 ──────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("상태이상 적용 / 해제")

    if not crew_map:
        st.info("등록된 승무원 없음")
    elif not se_map:
        st.info("등록된 상태이상 없음 — 패턴 등록 페이지에서 먼저 등록해주세요.")
    else:
        sel2 = st.selectbox("승무원 선택", list(crew_map.keys()), key="se_crew")
        cid2 = crew_map[sel2]

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

        sel_se     = st.selectbox("적용할 상태이상", list(se_map.keys()), key="se_sel")
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

# ── 주사위 판정 ───────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("주사위 판정")

    if not crew_map:
        st.info("등록된 승무원 없음")
    else:
        roll_type = st.radio("판정 유형", ["캐릭터 어필 (단독 굴림)", "러너 대항 (스탯 비교)"],
                             horizontal=True, key="roll_type")

        if roll_type == "캐릭터 어필 (단독 굴림)":
            st.caption("1d(스탯×5) 굴림 → 고정 성공치 이상이면 성공")
            ra1, ra2, ra3 = st.columns([3, 2, 2])
            appeal_crew  = ra1.selectbox("승무원", list(crew_map.keys()), key="appeal_crew")
            appeal_stat  = ra2.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="appeal_stat")
            appeal_thr   = ra3.number_input("성공치", min_value=1, value=10, key="appeal_thr")

            if st.button("판정", key="btn_appeal"):
                s, d = api("post", "/runners/crew/roll/appeal", json={
                    "crew_id":   crew_map[appeal_crew],
                    "stat":      STAT_OPTIONS[appeal_stat],
                    "threshold": int(appeal_thr),
                })
                if s == 200:
                    result_ko = "성공" if d["success"] else "실패"
                    st.code(
                        f"{d['crew_name']} — {appeal_stat} 어필\n"
                        f"{d['dice']} → {d['roll']} vs {d['threshold']}  →  {result_ko}",
                        language=None,
                    )
                else:
                    st.error(d)

        else:
            st.caption("각자 1d(스탯×5) 굴림 → 높은 쪽 승리. 데미지 없음.")
            names = list(crew_map.keys())
            rv1, rv2, rv3 = st.columns([3, 3, 2])
            vs_a    = rv1.selectbox("승무원 A", names, key="vs_a")
            vs_b    = rv2.selectbox("승무원 B", [n for n in names if n != vs_a], key="vs_b")
            vs_stat = rv3.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="vs_stat")

            if st.button("대항 판정", key="btn_vs"):
                s, d = api("post", "/runners/crew/roll/vs-runner", json={
                    "crew_a_id": crew_map[vs_a],
                    "crew_b_id": crew_map[vs_b],
                    "stat":      STAT_OPTIONS[vs_stat],
                })
                if s == 200:
                    st.code(
                        f"[ {vs_stat} 대항 ]\n"
                        f"{d['crew_a']}  {d['dice_a']} → {d['roll_a']}\n"
                        f"{d['crew_b']}  {d['dice_b']} → {d['roll_b']}\n\n"
                        f"승리: {d['winner']}",
                        language=None,
                    )
                else:
                    st.error(d)
