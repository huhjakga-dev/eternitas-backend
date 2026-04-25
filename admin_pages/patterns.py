import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("패턴 등록")

tabs = st.tabs(["전조 패턴", "재격리 패턴", "상태이상", "특수 기믹"])

_, cargos_data = api("get", "/runners/cargo")
_, se_data     = api("get", "/runners/status-effects")
cargos_data = cargos_data if isinstance(cargos_data, list) else []
se_data     = se_data     if isinstance(se_data,     list) else []
cargo_map   = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}
se_map      = {se["name"]: se["status_effect_id"] for se in se_data}

_STAT_KO    = {
    "health": "체력", "mentality": "정신력", "strength": "근력",
    "inteligence": "지력", "luckiness": "행운",
}
STAT_OPTIONS = {v: k for k, v in _STAT_KO.items()}

# ── 전조 패턴 ─────────────────────────────────────────────────────────────────
with tabs[0]:
    st.subheader("화물 전조 패턴 등록")

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        sel_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="pattern_cargo")
        cargo_id  = cargo_map[sel_cargo]

        _, existing_patterns = api("get", f"/runners/cargo/{cargo_id}/patterns")
        existing_patterns = existing_patterns if isinstance(existing_patterns, list) else []
        if existing_patterns:
            with st.expander(f"현재 등록된 패턴 ({len(existing_patterns)}개)", expanded=True):
                for p in existing_patterns:
                    st.markdown(f"- **{p['pattern_name']}** — {p.get('description', '') or '설명 없음'}")
        else:
            st.info("등록된 패턴 없음")

        st.divider()

        pattern_name = st.text_input("패턴 이름", key="pattern_name")
        description  = st.text_area("전조 현상 설명 (작업 때 나올 내용)", key="pattern_desc")
        answer       = st.text_area("전조 현상에 대한 정답", key="pattern_answer")

        st.markdown("**버프 (성공 시, 양수로 입력)**")
        bc1, bc2, bc3, bc4, bc5 = st.columns(5)
        buff_hp   = bc1.number_input("체력",   value=0.0, step=0.1, key="buff_hp")
        buff_sp   = bc2.number_input("정신력", value=0.0, step=0.1, key="buff_sp")
        buff_str  = bc3.number_input("근력",   value=0.0, step=0.1, key="buff_str")
        buff_int  = bc4.number_input("지력",   value=0.0, step=0.1, key="buff_int")
        buff_luck = bc5.number_input("행운",   value=0.0, step=0.1, key="buff_luck")
        buff_dmg_red = st.number_input("데미지 감소율 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="buff_dmg_red")

        st.markdown("**디버프 (실패 시, 음수로 입력)**")
        dc1, dc2, dc3, dc4, dc5 = st.columns(5)
        debuff_hp   = dc1.number_input("체력",   value=0.0, step=0.1, key="debuff_hp")
        debuff_sp   = dc2.number_input("정신력", value=0.0, step=0.1, key="debuff_sp")
        debuff_str  = dc3.number_input("근력",   value=0.0, step=0.1, key="debuff_str")
        debuff_int  = dc4.number_input("지력",   value=0.0, step=0.1, key="debuff_int")
        debuff_luck = dc5.number_input("행운",   value=0.0, step=0.1, key="debuff_luck")
        debuff_dmg_inc = st.number_input("데미지 증가율 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="debuff_dmg_inc")
        instant_kill = st.checkbox("대실패 즉사 기믹 ON", value=False, key="instant_kill")

        if st.button("패턴 추가", key="btn_pattern_add"):
            if not pattern_name.strip():
                st.error("패턴 이름을 입력해주세요.")
            else:
                status, data = api("post", "/runners/cargo/pattern", json={
                    "cargo_id": cargo_id, "pattern_name": pattern_name,
                    "description": description, "answer": answer,
                    "buff_stat_json": {"health": buff_hp, "mentality": buff_sp, "strength": buff_str, "inteligence": buff_int, "luckiness": buff_luck},
                    "buff_damage_reduction": buff_dmg_red,
                    "debuff_stat_json": {"health": debuff_hp, "mentality": debuff_sp, "strength": debuff_str, "inteligence": debuff_int, "luckiness": debuff_luck},
                    "debuff_demage_increase": debuff_dmg_inc,
                    "instant_kill": instant_kill,
                })
                if status in (200, 201):
                    st.success(f"패턴 '{pattern_name}' 추가 완료!")
                    st.rerun()
                else:
                    st.error(data)

# ── 재격리 패턴 ───────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("재격리 패턴 등록")

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        rp_cargo    = st.selectbox("화물 선택", list(cargo_map.keys()), key="rp_cargo")
        rp_cargo_id = cargo_map[rp_cargo]

        _, rp_existing = api("get", f"/reisolation/cargo/{rp_cargo_id}/patterns")
        rp_existing = rp_existing if isinstance(rp_existing, list) else []
        if rp_existing:
            with st.expander(f"현재 등록된 패턴 ({len(rp_existing)}개)", expanded=True):
                for p in rp_existing:
                    st.markdown(f"- **{p['pattern_name']}** — {p.get('description') or '설명 없음'}")
        else:
            st.info("등록된 패턴 없음")

        st.divider()
        rp_name = st.text_input("패턴 이름", key="rp_name")
        rp_desc = st.text_area("패턴 설명", key="rp_desc")
        rp_stat = st.selectbox("판정 스탯 (없으면 '없음')", ["없음"] + list(STAT_OPTIONS.keys()), key="rp_stat")
        rp_cfr  = st.slider("대실패 확률", 0.0, 1.0, 0.05, 0.01, key="rp_cfr")

        st.markdown("---")

        _EFFECT_SECTIONS = [
            ("unc",  "무조건 효과 (판정 무관 항상 적용)"),
            ("suc",  "성공 효과"),
            ("fail", "실패 효과"),
            ("cf",   "대실패 효과"),
        ]
        for _pfx, _ in _EFFECT_SECTIONS:
            if f"effects_{_pfx}" not in st.session_state:
                st.session_state[f"effects_{_pfx}"] = []

        def _effect_builder(prefix: str, label: str) -> list:
            st.markdown(f"**{label}**")
            key     = f"effects_{prefix}"
            effects = st.session_state[key]

            for i, eff in enumerate(effects):
                c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
                eff["type"]   = c1.selectbox("유형", ["instant_kill", "status_effect", "damage", "resolve"],
                                              index=["instant_kill","status_effect","damage","resolve"].index(eff.get("type","instant_kill")),
                                              key=f"{prefix}_t{i}")
                eff["target"] = c2.selectbox("대상", ["random", "all"],
                                              index=["random","all"].index(eff.get("target","random")),
                                              key=f"{prefix}_g{i}")
                if eff["type"] == "status_effect":
                    if se_map:
                        se_names = list(se_map.keys())
                        cur_id   = eff.get("status_effect_id", "")
                        cur_name = next((n for n, sid in se_map.items() if sid == cur_id), se_names[0])
                        sel_name = c3.selectbox("상태이상", se_names,
                                                 index=se_names.index(cur_name),
                                                 key=f"{prefix}_se{i}")
                        eff["status_effect_id"] = se_map[sel_name]
                    else:
                        c3.caption("등록된 상태이상 없음")
                        eff["status_effect_id"] = ""
                    eff.pop("amount", None); eff.pop("damage_type", None)
                elif eff["type"] == "damage":
                    eff["amount"]      = c3.number_input("데미지량", 1, 999, eff.get("amount", 10), key=f"{prefix}_amt{i}")
                    eff["damage_type"] = st.selectbox("데미지 타입", ["hp","sp","both"],
                                                       index=["hp","sp","both"].index(eff.get("damage_type","hp")),
                                                       key=f"{prefix}_dt{i}")
                    eff.pop("status_effect_id", None)
                else:
                    eff.pop("status_effect_id", None); eff.pop("amount", None); eff.pop("damage_type", None)
                if c4.button("삭제", key=f"{prefix}_del{i}"):
                    st.session_state[key].pop(i)
                    st.rerun()

            if st.button(f"+ 효과 추가 ({label})", key=f"btn_{prefix}_add"):
                st.session_state[key].append({"type": "instant_kill", "target": "random"})
                st.rerun()

            return [{k: v for k, v in e.items() if v not in (None, "")} for e in effects]

        unc_effects  = _effect_builder("unc",  "무조건 효과 (판정 무관 항상 적용)")
        suc_effects  = _effect_builder("suc",  "성공 효과")
        fail_effects = _effect_builder("fail", "실패 효과")
        cf_effects   = _effect_builder("cf",   "대실패 효과")

        if st.button("패턴 등록", key="btn_rp_add"):
            if not rp_name.strip():
                st.error("패턴 이름을 입력해주세요.")
            else:
                s, d = api("post", "/reisolation/patterns", json={
                    "cargo_id":                rp_cargo_id,
                    "pattern_name":            rp_name.strip(),
                    "description":             rp_desc.strip() or None,
                    "stat":                    STAT_OPTIONS.get(rp_stat) if rp_stat != "없음" else None,
                    "critical_fail_rate":      rp_cfr,
                    "unconditional_effects":   unc_effects,
                    "on_success_effects":      suc_effects,
                    "on_fail_effects":         fail_effects,
                    "on_critical_fail_effects": cf_effects,
                })
                if s in (200, 201):
                    st.success(f"패턴 '{d.get('pattern_name')}' 등록 완료!")
                    for _pfx, _ in _EFFECT_SECTIONS:
                        st.session_state[f"effects_{_pfx}"] = []
                    st.rerun()
                else:
                    st.error(d)

# ── 상태이상 등록 ─────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("상태이상 등록")

    if se_data:
        with st.expander(f"등록된 상태이상 ({len(se_data)}개)", expanded=False):
            for se in se_data:
                tick_info = ""
                if se.get("tick_damage"):
                    tick_info = f" | {se['tick_interval_minutes']}분마다 -{se['tick_damage']}"
                st.markdown(f"- **{se['name']}**{tick_info} — {se.get('description') or '설명 없음'}")
    else:
        st.info("등록된 상태이상 없음")

    st.divider()

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        se_name = st.text_input("상태이상 이름", key="se_name")
        se_desc = st.text_input("설명 (선택)", key="se_desc")

        st.markdown("**스탯 영향** (양수=버프, 음수=디버프)")
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        se_hp   = sc1.number_input("체력",   value=0.0, step=0.1, key="se_hp")
        se_sp   = sc2.number_input("정신력", value=0.0, step=0.1, key="se_sp")
        se_str  = sc3.number_input("근력",   value=0.0, step=0.1, key="se_str")
        se_int  = sc4.number_input("지력",   value=0.0, step=0.1, key="se_int")
        se_luck = sc5.number_input("행운",   value=0.0, step=0.1, key="se_luck")

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
        se_duration  = ex1.number_input("지속 시간 (분, 0=무제한)", min_value=0, value=0, key="se_duration")
        se_max_ticks = ex2.number_input("최대 틱 횟수 (0=무제한)", min_value=0, value=0, key="se_max_ticks")
        if se_duration or se_max_ticks:
            parts = []
            if se_duration:  parts.append(f"{se_duration}분 경과")
            if se_max_ticks: parts.append(f"틱 {se_max_ticks}회 도달")
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
                    st.rerun()
                else:
                    st.error(d)

# ── 특수 기믹 등록 ────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("화물 특수 기믹 등록")
    st.caption("작업 진행 화면에서 수동으로 실행하는 특수 효과입니다.")

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        gm_cargo       = st.selectbox("화물 선택", list(cargo_map.keys()), key="gm_cargo")
        gm_cargo_id    = cargo_map[gm_cargo]

        _, gm_existing = api("get", f"/runners/cargo/{gm_cargo_id}/gimmicks")
        gm_existing = gm_existing if isinstance(gm_existing, list) else []
        if gm_existing:
            with st.expander(f"현재 등록된 기믹 ({len(gm_existing)}개)", expanded=True):
                _OP_KO2 = {"lte": "이하", "lt": "미만", "gte": "이상", "gt": "초과", "eq": "동일"}
                for gm in gm_existing:
                    if gm["action_type"] == "kill_if_stat":
                        desc = f"[{gm['stat']} {_OP_KO2.get(gm.get('operator',''),'?')} {gm.get('threshold','?')}] 즉사"
                    elif gm["action_type"] == "apply_damage":
                        desc = f"[{gm.get('damage_type','hp').upper()} {gm.get('amount','?')} 피해]"
                    else:
                        desc = "[상태이상 적용]"
                    col_n, col_d, col_rm = st.columns([3, 4, 1])
                    col_n.write(f"**{gm['name']}**")
                    col_d.caption(f"{desc}  {gm.get('description') or ''}")
                    if col_rm.button("삭제", key=f"gm_del_{gm['gimmick_id']}"):
                        rs, rd = api("delete", f"/runners/cargo/{gm_cargo_id}/gimmicks/{gm['gimmick_id']}")
                        if rs == 200:
                            st.rerun()
                        else:
                            st.error(rd)
        else:
            st.info("등록된 기믹 없음")

        st.divider()

        gm_name       = st.text_input("기믹 이름", key="gm_name")
        gm_desc       = st.text_input("설명 (선택)", key="gm_desc")
        gm_sort       = st.number_input("실행 순서", min_value=0, value=0, step=1, key="gm_sort")

        _ACTION_OPTS = {
            "스탯 조건 즉사": "kill_if_stat",
            "고정 피해":       "apply_damage",
            "상태이상 적용":   "apply_status_effect",
        }
        gm_action_ko  = st.selectbox("효과 유형", list(_ACTION_OPTS.keys()), key="gm_action")
        gm_action     = _ACTION_OPTS[gm_action_ko]

        gm_stat = gm_op = gm_threshold = None
        gm_amount = gm_dmg_type = None
        gm_se_id = None

        if gm_action == "kill_if_stat":
            _OP_OPTS = {"이하 (≤)": "lte", "미만 (<)": "lt", "이상 (≥)": "gte", "초과 (>)": "gt", "동일 (=)": "eq"}
            ka1, ka2, ka3 = st.columns([2, 2, 2])
            gm_stat_ko    = ka1.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="gm_stat")
            gm_op_ko      = ka2.selectbox("조건",      list(_OP_OPTS.keys()),     key="gm_op")
            gm_threshold  = ka3.number_input("임계값", min_value=0, value=6,      key="gm_threshold")
            gm_stat       = STAT_OPTIONS[gm_stat_ko]
            gm_op         = _OP_OPTS[gm_op_ko]
            st.caption(f"→ {gm_stat_ko}이 {gm_op_ko.split('(')[0].strip()} {gm_threshold}인 승무원 즉사")

        elif gm_action == "apply_damage":
            kd1, kd2 = st.columns(2)
            gm_amount   = kd1.number_input("피해량", min_value=1, value=10, key="gm_amount")
            gm_dmg_type = kd2.selectbox("피해 유형", ["hp", "sp", "both"], key="gm_dmg_type",
                                         format_func=lambda x: {"hp":"HP","sp":"SP","both":"HP·SP"}[x])

        elif gm_action == "apply_status_effect":
            if not se_map:
                st.warning("등록된 상태이상이 없습니다.")
            else:
                gm_se_name = st.selectbox("적용할 상태이상", list(se_map.keys()), key="gm_se")
                gm_se_id   = se_map[gm_se_name]

        if st.button("기믹 등록", key="btn_gm_reg"):
            if not gm_name.strip():
                st.error("기믹 이름을 입력해주세요.")
            elif gm_action == "kill_if_stat" and gm_stat is None:
                st.error("스탯을 선택해주세요.")
            elif gm_action == "apply_status_effect" and not gm_se_id:
                st.error("상태이상을 선택해주세요.")
            else:
                s, d = api("post", f"/runners/cargo/{gm_cargo_id}/gimmicks", json={
                    "name":             gm_name.strip(),
                    "description":      gm_desc or None,
                    "action_type":      gm_action,
                    "stat":             gm_stat,
                    "operator":         gm_op,
                    "threshold":        int(gm_threshold) if gm_threshold is not None else None,
                    "amount":           int(gm_amount) if gm_amount else None,
                    "damage_type":      gm_dmg_type,
                    "status_effect_id": gm_se_id,
                    "sort_order":       int(gm_sort),
                })
                if s in (200, 201):
                    st.success(f"기믹 '{d.get('name')}' 등록 완료!")
                    st.rerun()
                else:
                    st.error(d)
