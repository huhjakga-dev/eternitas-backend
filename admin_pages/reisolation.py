import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("재격리 관리")

tabs = st.tabs(["세션 목록", "세션 생성", "공격 판정", "패턴 등록", "패턴 이벤트", "승무원 전투", "탈출 처리"])

_, crews_data    = api("get", "/runners/crew")
_, cargos_data   = api("get", "/runners/cargo")
_, sessions_data = api("get", "/reisolation/sessions")

crews_data    = crews_data    if isinstance(crews_data, list)    else []
cargos_data   = cargos_data   if isinstance(cargos_data, list)   else []
sessions_data = sessions_data if isinstance(sessions_data, list) else []

crew_map      = {c["crew_name"]: c["crew_id"]   for c in crews_data}
cargo_map     = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}
cargo_id_name = {c["cargo_id"]: c["cargo_name"] for c in cargos_data}
escaped_cargos = {c["cargo_name"]: c["cargo_id"] for c in cargos_data if c.get("is_escaped")}

active_sessions = [s for s in sessions_data if s["status"] == "active"]

_STAT_KO = {
    "health": "체력", "mentality": "정신력", "strength": "근력",
    "inteligence": "지력", "luckiness": "행운",
}
_RESULT_KO = {
    "success": "성공", "fail": "실패", "critical_fail": "대실패",
}
STAT_OPTIONS = {v: k for k, v in _STAT_KO.items()}

GRADE_WEIGHT = {"standard": 5, "non_standard": 15, "overload": 30, "fixed": 50}
GRADE_HP     = {"standard": 100, "non_standard": 230, "overload": 330, "fixed": 500}


def session_label(s):
    return f"{cargo_id_name.get(s['cargo_id'], s['cargo_id'][:8])} — {s['session_id'][:8]}… (HP {s['cargo_current_hp']}/{s['cargo_max_hp']})"


session_map   = {session_label(s): s["session_id"] for s in active_sessions}
session_cargo = {s["session_id"]: s["cargo_id"]    for s in active_sessions}


def _fmt_apply_pattern(data: dict) -> str:
    lines = ["■ 재격리 패턴 적용 결과", f"패턴: {data.get('pattern_name', '')}", ""]

    roll_details  = data.get("roll_details", {})
    crew_results  = data.get("crew_results", {})
    effects       = data.get("effects_applied", [])
    resolved      = data.get("resolved", False)

    if roll_details:
        lines.append("[ 판정 결과 ]")
        for name, detail in roll_details.items():
            result_ko = _RESULT_KO.get(crew_results.get(name, ""), crew_results.get(name, "-"))
            lines.append(
                f"  {name}: {detail['dice']} → {detail['roll']} vs {detail['vs']}  →  {result_ko}"
            )
        lines.append("")
    elif crew_results:
        lines.append("[ 판정 결과 ]")
        for name, result in crew_results.items():
            lines.append(f"  {name}: {_RESULT_KO.get(result, result or '-')}")
        lines.append("")

    if effects:
        lines.append("[ 적용된 효과 ]")
        for e in effects:
            lines.append(f"  {e}")
        lines.append("")

    lines.append(f"■ 세션 종료: {'예 — 재격리 완료' if resolved else '아니오'}")
    return "\n".join(lines)


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
- 굴림: ({d['crew_roll']}) + {d['hit_bonus']} = **{d['final_roll']}** vs {d['threshold']} → **{success_str}**
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

# ── 패턴 등록 ─────────────────────────────────────────────────────────────────
with tabs[3]:
    st.subheader("재격리 패턴 등록")

    if not cargo_map:
        st.warning("등록된 화물이 없습니다.")
    else:
        rp_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="rp_cargo")
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
            key = f"effects_{prefix}"
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
                    eff["status_effect_id"] = c3.text_input("상태이상 ID", value=eff.get("status_effect_id",""), key=f"{prefix}_se{i}")
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

# ── 패턴 이벤트 ───────────────────────────────────────────────────────────────
with tabs[4]:
    st.subheader("패턴 이벤트 적용")

    if not session_map:
        st.info("진행 중인 재격리 세션 없음")
    else:
        pe_session_label = st.selectbox("세션 선택", list(session_map.keys()), key="pe_session")
        pe_sid      = session_map[pe_session_label]
        pe_cargo_id = session_cargo[pe_sid]

        _, pe_patterns = api("get", f"/reisolation/cargo/{pe_cargo_id}/patterns")
        pe_patterns = pe_patterns if isinstance(pe_patterns, list) else []
        pe_pattern_map = {p["pattern_name"]: p["pattern_id"] for p in pe_patterns}

        if not pe_pattern_map:
            st.warning("해당 화물에 등록된 재격리 패턴 없음")
        else:
            pe_pattern_label = st.selectbox("패턴 선택", list(pe_pattern_map.keys()), key="pe_pattern")
            pe_pattern_info  = next((p for p in pe_patterns if p["pattern_name"] == pe_pattern_label), {})

            if pe_pattern_info.get("description"):
                st.caption(pe_pattern_info["description"])

            pe_crews = st.multiselect("대상 승무원", list(crew_map.keys()), key="pe_crews")

            # 판정 스탯 (optional)
            pe_use_stat = st.checkbox("주사위 판정 사용", key="pe_use_stat")
            pe_stat = None
            if pe_use_stat:
                pe_stat_label = st.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="pe_stat")
                pe_stat = STAT_OPTIONS[pe_stat_label]

            # 대응지문 판정 (optional)
            pe_use_response = st.checkbox("대응지문 판정 사용", key="pe_use_response")
            pe_response = None
            if pe_use_response:
                pe_resp_val = st.radio("대응지문 결과", ["성공", "실패"], horizontal=True, key="pe_resp_val")
                pe_response = pe_resp_val == "성공"

            if st.button("패턴 적용", key="btn_pe_apply"):
                s, d = api("post", f"/reisolation/sessions/{pe_sid}/apply-pattern", json={
                    "pattern_id":       pe_pattern_map[pe_pattern_label],
                    "crew_ids":         [crew_map[c] for c in pe_crews],
                    "stat":             pe_stat,
                    "response_success": pe_response,
                })
                if s == 200:
                    st.code(_fmt_apply_pattern(d), language=None)
                    if d.get("resolved"):
                        st.rerun()
                else:
                    st.error(d)

# ── 승무원 vs 승무원 전투 ─────────────────────────────────────────────────────
with tabs[5]:
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
with tabs[6]:
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
