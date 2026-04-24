import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("작업 관리")

tabs = st.tabs(["세션 목록", "세션 생성", "전조 진행", "본 작업"])

_STAT_KO = {
    "health": "체력", "mentality": "정신력", "strength": "근력",
    "inteligence": "지력", "luckiness": "행운",
}
_STAT_KO_UP = {k.upper(): v for k, v in _STAT_KO.items()}
_DMG_KO     = {"hp": "HP", "sp": "SP", "both": "HP·SP"}
_RESULT_KO  = {
    "success": "성공", "invalid": "무효", "fail": "실패", "critical_fail": "대실패",
}

STAT_OPTIONS = {v: k for k, v in _STAT_KO.items()}


def _show_copyable(text: str):
    """서술형 결과를 복사 가능한 코드 블록으로 표시."""
    st.code(text, language=None)


def _fmt_precursor(pattern_name: str, stat_ko: str, data: dict) -> str:
    result_val     = data.get("result", "")
    result_str     = _RESULT_KO.get(result_val, result_val)
    roll           = data.get("roll_detail", {})
    applied        = data.get("applied_effect", {})
    kill_detail    = data.get("kill_detail")
    session_status = data.get("session_status", "")

    lines = ["■ 전조 판정 결과", f"패턴: {pattern_name}", ""]

    if roll:
        lines.append(
            f"판정 스탯: {stat_ko}  |  "
            f"승무원 주사위 {roll.get('crew_roll', '?')} vs 화물 고정값 {roll.get('cargo_fixed', '?')}"
        )
    lines.append(f"결과: {result_str}")

    if kill_detail:
        lines.append(f"→ {kill_detail}")

    effect_lines = []
    for k, v in applied.items():
        if v == 0:
            continue
        if k == "_damage_modifier":
            if v < 0:
                effect_lines.append(f"  데미지 {abs(v) * 100:.0f}% 감소")
            else:
                effect_lines.append(f"  데미지 {v * 100:.0f}% 증가")
        else:
            ko = _STAT_KO.get(k, k)
            sign = "+" if v > 0 else ""
            effect_lines.append(f"  {ko} {sign}{int(v) if v == int(v) else v}")

    if effect_lines:
        lines += ["", "적용 효과:"] + effect_lines

    lines += ["", f"세션 상태: {session_status}"]
    return "\n".join(lines)


def _fmt_main_work(crew_name: str, damage_type: str, data: dict) -> str:
    summary         = data.get("summary", [])
    damage_per_crew = data.get("damage_per_crew", {})
    session_result  = data.get("session_result")
    session_status  = data.get("session_status", "")
    dmg_ko          = _DMG_KO.get(damage_type, "HP")

    lines          = []
    total_ok       = 0
    total_fail_cnt = 0

    for block in summary:
        if not block or not block.startswith("["):
            lines.append(block)
            continue

        bracket_end = block.index("]")
        stat_key    = block[1:bracket_end]
        stat_ko     = _STAT_KO_UP.get(stat_key, stat_key)
        turns       = block[bracket_end + 2:].split(" / ")

        block_ok   = sum(1 for t in turns if ": 성공" in t)
        block_fail = sum(1 for t in turns if ": 실패" in t)
        total_ok       += block_ok
        total_fail_cnt += block_fail

        lines.append(f"{crew_name}의 {stat_ko} 스탯으로 {block_ok + block_fail}턴 작업.")
        for turn in turns:
            lines.append(turn)
        lines.append(f"성공 {block_ok}턴, 실패 {block_fail}턴")
        lines.append("")

    # 데미지 집계
    if damage_per_crew:
        total_dmg = sum(damage_per_crew.values())
        if total_dmg:
            lines.append(f"총 {dmg_ko} 데미지: {total_dmg}")
            if len(damage_per_crew) > 1:
                for name, dmg in damage_per_crew.items():
                    if dmg:
                        lines.append(f"  {name}: {dmg}")

    # 최종 결과
    if session_result:
        lines.append("")
        lines.append(f"■ {session_result}")
    else:
        lines.append(f"\n세션 상태: {session_status}")

    return "\n".join(lines)


# ── 공통 데이터 로드 ──────────────────────────────────────────────────────────
_, crews_data    = api("get", "/runners/crew")
_, cargos_data   = api("get", "/runners/cargo")
_, sessions_data = api("get", "/works/sessions")

crews_data    = crews_data    if isinstance(crews_data, list)    else []
cargos_data   = cargos_data   if isinstance(cargos_data, list)   else []
sessions_data = sessions_data if isinstance(sessions_data, list) else []

crew_map         = {c["crew_name"]: c["crew_id"]  for c in crews_data}
cargo_map        = {c["cargo_name"]: c["cargo_id"] for c in cargos_data}
cargo_dmg_type   = {c["cargo_id"]: c.get("damage_type", "hp") for c in cargos_data}
cargo_id_to_name = {c["cargo_id"]: c["cargo_name"] for c in cargos_data}


def _session_label(s):
    name = cargo_id_to_name.get(s["cargo_id"], s["cargo_id"][:8])
    return f"[{s['status']}] {name} — {s['id'][:8]}…"


active_sessions = [s for s in sessions_data if s["status"] != "resolved"]
session_map     = {_session_label(s): s["id"]         for s in active_sessions}
session_cargo   = {s["id"]:           s["cargo_id"]   for s in active_sessions}

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
        sel_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="new_cargo")
        sel_crews = st.multiselect("참여 승무원 (최대 3명)", list(crew_map.keys()), max_selections=3, key="new_crews")

        if st.button("세션 생성"):
            status, data = api("post", "/works/sessions", json={
                "cargo_id": cargo_map[sel_cargo],
                "crew_ids": [crew_map[c] for c in sel_crews],
            })
            if status in (200, 201):
                st.success(f"세션 생성 완료 — ID: {data.get('id', '')}")
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
        pre_cargo_id      = session_cargo[pre_sid]

        _, patterns_data = api("get", f"/runners/cargo/{pre_cargo_id}/patterns")
        patterns_data = patterns_data if isinstance(patterns_data, list) else []
        pattern_map   = {p["pattern_name"]: p["pattern_id"] for p in patterns_data}

        if not pattern_map:
            st.warning("해당 화물에 등록된 패턴 없음")
        else:
            pre_pattern_label = st.selectbox("패턴 선택", list(pattern_map.keys()), key="pre_pattern")
            pre_crew_label    = st.selectbox("판정 승무원", list(crew_map.keys()), key="pre_crew")
            pre_stat_label    = st.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="pre_stat")
            pre_success       = st.radio("승무원 성공 여부", ["성공", "실패"], horizontal=True, key="pre_success")

            if st.button("전조 판정"):
                status, data = api("post", f"/works/sessions/{pre_sid}/precursor-calculate", json={
                    "pattern_id": pattern_map[pre_pattern_label],
                    "crew_id":    crew_map[pre_crew_label],
                    "stat":       STAT_OPTIONS[pre_stat_label],
                    "is_success": pre_success == "성공",
                })
                if status == 200:
                    formatted = _fmt_precursor(pre_pattern_label, pre_stat_label, data)
                    _show_copyable(formatted)
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
        work_cargo_id      = session_cargo[work_sid]
        work_dmg_type      = cargo_dmg_type.get(work_cargo_id, "hp")
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
                formatted = _fmt_main_work(work_crew_label, work_dmg_type, data)
                _show_copyable(formatted)
            else:
                st.error(data)
