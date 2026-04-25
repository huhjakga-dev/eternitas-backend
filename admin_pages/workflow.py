import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("작업 진행")

# ── 공통 데이터 ───────────────────────────────────────────────────────────────
_, crews_data  = api("get", "/runners/crew")
_, cargos_data = api("get", "/runners/cargo")
crews_data  = crews_data  if isinstance(crews_data,  list) else []
cargos_data = cargos_data if isinstance(cargos_data, list) else []

def _cargo_label(c: dict) -> str:
    code = c.get("cargo_code") or ""
    return f"({code}) {c['cargo_name']}" if code else c["cargo_name"]

crew_map      = {c["crew_name"]:  c["crew_id"]  for c in crews_data}
alive_crew_set = {c["crew_name"] for c in crews_data if not c.get("is_dead")}
cargo_map   = {_cargo_label(c):   c["cargo_id"] for c in cargos_data}
cargo_by_id = {c["cargo_id"]:     c             for c in cargos_data}
escaped_map = {_cargo_label(c):   c["cargo_id"] for c in cargos_data if c.get("is_escaped")}
# 세션 저장용: label → cargo_name
cargo_name_by_label = {_cargo_label(c): c["cargo_name"] for c in cargos_data}

_STAT_KO   = {"health": "체력", "mentality": "정신력", "strength": "근력",
               "inteligence": "지력", "luckiness": "행운"}
_DMG_KO    = {"hp": "HP", "sp": "SP", "both": "HP·SP"}
STAT_OPTIONS = {v: k for k, v in _STAT_KO.items()}
_RMAP        = {"성공": "success", "실패": "fail", "대실패": "critical_fail"}

# ── session_state 초기화 ──────────────────────────────────────────────────────
if "work_sessions" not in st.session_state:
    st.session_state.work_sessions = {}   # {sid: {cargo_id, cargo_name, ...}}
if "ri_sid"           not in st.session_state: st.session_state.ri_sid           = None
if "ri_cargo_id"      not in st.session_state: st.session_state.ri_cargo_id      = None
if "ri_session_crews" not in st.session_state: st.session_state.ri_session_crews = []
if "ri_results"       not in st.session_state: st.session_state.ri_results       = []


def _new_session_state(cargo_id: str, cargo_name: str, crews: list) -> dict:
    return {
        "cargo_id":      cargo_id,
        "cargo_name":    cargo_name,
        "crews":         crews,
        "sess_status":   "waiting_precursor",
        "pre_hint":      None,
        "results":       [],
        "submitted":     [],
        "totals":        {"planned": 0, "success": 0},
        "resolved":      False,
        "commands":      [{"stat": "health", "count": 1}],
    }


def _add_result(ss: dict, text: str):
    ss["results"].append({"text": text, "dismissed": False})


def _show_results(ss: dict, prefix: str):
    for i, r in enumerate(ss["results"]):
        if r["dismissed"]:
            continue
        with st.container(border=True):
            st.code(r["text"], language=None)
            if st.button("닫기", key=f"{prefix}_close_{i}"):
                ss["results"][i]["dismissed"] = True
                st.rerun()


def _fmt_main_work(crew_name: str, dmg_type: str, d: dict) -> str:
    summary = d.get("summary", [])
    dmg_map = d.get("damage_per_crew", {})
    dmg_ko  = _DMG_KO.get(dmg_type, "HP")
    lines   = [f"■ {crew_name} 작업 결과", ""]
    for block in summary:
        if not block or not block.startswith("["):
            lines.append(block)
            continue
        bk_end   = block.index("]")
        stat_key = block[1:bk_end]
        stat_ko  = _STAT_KO.get(stat_key.lower(), stat_key)
        turns    = block[bk_end + 2:].split(" / ")
        ok   = sum(1 for t in turns if ": 성공" in t)
        fail = sum(1 for t in turns if ": 실패" in t)
        lines.append(f"[{stat_ko}]  {ok + fail}턴  (성공 {ok} / 실패 {fail})")
        lines.extend(turns)
        lines.append("")
    total_dmg = sum(dmg_map.values())
    if total_dmg:
        lines.append(f"총 {dmg_ko} 피해: {total_dmg}")
        if len(dmg_map) > 1:
            for name, dmg in dmg_map.items():
                if dmg:
                    lines.append(f"  {name}: {dmg}")
    if d.get("session_result"):
        lines.append(f"\n■ {d['session_result']}")
    return "\n".join(lines)


# ── 탭 ────────────────────────────────────────────────────────────────────────
tab_work, tab_ri, tab_crew = st.tabs(["화물 작업", "화물 재격리", "승무원 즉시 조치"])


# ══════════════════════════════════════════════════════════════════════════════
# 화물 작업
# ══════════════════════════════════════════════════════════════════════════════
with tab_work:

    # ── 세션 생성 폼 (항상 표시) ──────────────────────────────────────────────
    with st.expander("＋ 새 세션 생성", expanded=not st.session_state.work_sessions):
        if not cargo_map:
            st.warning("등록된 화물이 없습니다.")
        else:
            w_cargo = st.selectbox("화물 선택", list(cargo_map.keys()), key="w_cargo")
            w_crews = st.multiselect("참여 승무원 (최대 3명)", list(crew_map.keys()),
                                     max_selections=3, key="w_crews")
            if st.button("세션 생성", type="primary", key="btn_w_start"):
                s, d = api("post", "/works/sessions", json={
                    "cargo_id": cargo_map[w_cargo],
                    "crew_ids": [crew_map[c] for c in w_crews],
                })
                if s in (200, 201):
                    new_sid = d["id"]
                    st.session_state.work_sessions[new_sid] = _new_session_state(
                        cargo_map[w_cargo], cargo_name_by_label[w_cargo], w_crews
                    )
                    st.rerun()
                else:
                    st.error(d)

    # ── 활성 세션 목록 ────────────────────────────────────────────────────────
    for sid, ss in list(st.session_state.work_sessions.items()):
        cargo_info  = cargo_by_id.get(ss["cargo_id"], {})
        is_resolved = ss["resolved"]
        sess_status = ss["sess_status"] or "waiting_precursor"
        dmg_type    = cargo_info.get("damage_type", "hp")
        session_crews       = ss["crews"] or list(crew_map.keys())
        alive_session_crews = [c for c in session_crews if c in alive_crew_set]

        status_badge = "✓ 완료" if is_resolved else "● 진행 중"
        label = (
            f"{status_badge}  {ss['cargo_name']} ({cargo_info.get('grade','?')})  "
            f"|  총 턴수 {cargo_info.get('total_turns','?')}  "
            f"|  관측률 {cargo_info.get('observation_rate', 0):.0f}%  "
            f"|  `{sid[:8]}…`"
        )

        with st.expander(label, expanded=not is_resolved):

            # 닫기 버튼
            if st.button("세션 닫기", key=f"btn_close_{sid}"):
                del st.session_state.work_sessions[sid]
                st.rerun()

            st.divider()

            # 결과 표시
            _show_results(ss, f"wr_{sid}")

            # ── 특수 기믹 ─────────────────────────────────────────────────
            _, gimmicks_data = api("get", f"/runners/cargo/{ss['cargo_id']}/gimmicks")
            gimmicks_data = gimmicks_data if isinstance(gimmicks_data, list) else []

            if gimmicks_data and not is_resolved:
                st.subheader("⚙ 특수 기믹")
                _OP_KO3 = {"lte": "이하", "lt": "미만", "gte": "이상", "gt": "초과", "eq": "동일"}
                for gm in gimmicks_data:
                    with st.container(border=True):
                        gc1, gc2 = st.columns([5, 1])
                        if gm["action_type"] == "kill_if_stat":
                            detail = f"{gm.get('stat','')} {_OP_KO3.get(gm.get('operator',''),'')} {gm.get('threshold','')} → 즉사"
                        elif gm["action_type"] == "apply_damage":
                            calc = gm.get("damage_calc", "fixed")
                            dmg_lbl = _DMG_KO.get(gm.get('damage_type','hp'), 'HP')
                            if calc == "percent_hp":
                                detail = f"최대HP {gm.get('amount',0)}% {dmg_lbl} 피해"
                            elif calc == "percent_sp":
                                detail = f"최대SP {gm.get('amount',0)}% {dmg_lbl} 피해"
                            else:
                                detail = f"{dmg_lbl} {gm.get('amount', 0)} 피해"
                        else:
                            detail = "상태이상 적용"
                        gc1.markdown(f"**{gm['name']}** — {detail}")
                        if gm.get("description"):
                            gc1.caption(gm["description"])
                        if gc2.button("실행", key=f"btn_gm_{sid}_{gm['gimmick_id']}"):
                            s2, d2 = api("post", f"/works/sessions/{sid}/run-gimmick",
                                         json={"gimmick_id": gm["gimmick_id"]})
                            if s2 == 200:
                                _add_result(ss, d2["summary"])
                                st.rerun()
                            else:
                                st.error(d2)
                st.divider()

            # ── ① 전조 판정 ───────────────────────────────────────────────
            if not is_resolved and sess_status == "waiting_precursor":
                st.subheader("① 전조 판정")
                _, patterns_data = api("get", f"/runners/cargo/{ss['cargo_id']}/patterns")
                patterns_data = patterns_data if isinstance(patterns_data, list) else []
                pattern_labels = {
                    f"({p['pattern_id'][:8]}) {p['pattern_name']}": p["pattern_id"]
                    for p in patterns_data
                }
                pattern_map_local = {p["pattern_name"]: p["pattern_id"] for p in patterns_data}

                if not pattern_labels:
                    st.caption("등록된 전조 패턴 없음")
                    if st.button("전조 건너뛰고 본 작업으로", key=f"btn_skip_{sid}"):
                        ss["sess_status"] = "main_work_ready"
                        st.rerun()
                else:
                    hint       = ss["pre_hint"]
                    label_list = list(pattern_labels.keys())
                    hint_idx   = next(
                        (i for i, lbl in enumerate(label_list) if hint and hint in lbl), 0
                    )
                    pc1, pc2, pc3 = st.columns([3, 2, 2])
                    p_label    = pc1.selectbox("패턴 선택", label_list, index=hint_idx,
                                               key=f"pre_pattern_{sid}")
                    p_info     = next(p for p in patterns_data
                                      if p["pattern_id"] == pattern_labels[p_label])
                    p_name     = p_info["pattern_name"]
                    if p_info.get("description"):
                        pc1.caption(p_info["description"])
                    if p_info.get("answer"):
                        pc1.caption(f"📋 정답: {p_info['answer']}")
                    p_result   = pc2.radio("결과", ["성공", "실패", "대실패"],
                                           horizontal=True, key=f"pre_result_{sid}")
                    p_crew_lbl = pc3.selectbox("대응 승무원", alive_session_crews or session_crews,
                                               key=f"pre_crew_{sid}")

                    # 이 패턴에 연결된 기믹
                    _, p_gimmicks = api("get",
                        f"/runners/cargo/{ss['cargo_id']}/gimmicks",
                        params={"pattern_id": p_info["pattern_id"]})
                    p_gimmicks = p_gimmicks if isinstance(p_gimmicks, list) else []
                    if p_gimmicks:
                        st.caption("이 패턴에 연결된 기믹:")
                        _OP_KO4 = {"lte": "이하", "lt": "미만", "gte": "이상", "gt": "초과", "eq": "동일"}
                        for pgm in p_gimmicks:
                            with st.container(border=True):
                                pg1, pg2 = st.columns([5, 1])
                                if pgm["action_type"] == "kill_if_stat":
                                    detail = f"{pgm.get('stat','')} {_OP_KO4.get(pgm.get('operator',''),'')} {pgm.get('threshold','')} → 즉사"
                                elif pgm["action_type"] == "apply_damage":
                                    calc = pgm.get("damage_calc", "fixed")
                                    dmg_lbl = _DMG_KO.get(pgm.get('damage_type','hp'), 'HP')
                                    if calc == "percent_hp":
                                        detail = f"최대HP {pgm.get('amount',0)}% {dmg_lbl} 피해"
                                    elif calc == "percent_sp":
                                        detail = f"최대SP {pgm.get('amount',0)}% {dmg_lbl} 피해"
                                    else:
                                        detail = f"{dmg_lbl} {pgm.get('amount',0)} 피해"
                                else:
                                    detail = "상태이상 적용"
                                pg1.markdown(f"**{pgm['name']}** — {detail}")
                                if pgm.get("description"):
                                    pg1.caption(pgm["description"])
                                if pg2.button("실행", key=f"btn_pgm_{sid}_{pgm['gimmick_id']}"):
                                    s3, d3 = api("post", f"/works/sessions/{sid}/run-gimmick",
                                                 json={"gimmick_id": pgm["gimmick_id"]})
                                    if s3 == 200:
                                        _add_result(ss, d3["summary"])
                                        st.rerun()
                                    else:
                                        st.error(d3)

                    if st.button("전조 진행", key=f"btn_pre_{sid}"):
                        s2, d2 = api(
                            "post",
                            f"/works/cargo/{ss['cargo_id']}/precursor/{pattern_map_local[p_name]}",
                            json={
                                "session_id": sid,
                                "crew_id":    crew_map[p_crew_lbl],
                                "result":     _RMAP[p_result],
                            },
                        )
                        if s2 == 200:
                            _add_result(ss, d2.get("log_text", ""))
                            new_status = d2.get("session_status", sess_status)
                            ss["sess_status"] = new_status
                            ss["pre_hint"]    = d2.get("hint")
                            if d2.get("resolved") or new_status == "resolved":
                                ss["resolved"] = True
                            st.rerun()
                        else:
                            st.error(d2)
                st.divider()

            # ── ② 본 작업 ─────────────────────────────────────────────────
            if not is_resolved and sess_status == "waiting_precursor":
                st.info("전조 판정을 완료해야 본 작업을 진행할 수 있습니다.")

            elif not is_resolved and sess_status == "main_work_ready":
                st.subheader("② 본 작업")
                submitted = ss["submitted"]
                remaining = [c for c in session_crews if c not in submitted]

                if not remaining:
                    t = ss["totals"]
                    st.success(
                        f"모든 승무원 작업 완료  |  "
                        f"총 {t['planned']}턴  성공 {t['success']}턴 / 실패 {t['planned'] - t['success']}턴"
                    )
                else:
                    total_turns = cargo_info.get("total_turns", "?")
                    st.caption(
                        f"총 턴수: **{total_turns}**  |  "
                        f"남은 승무원: {', '.join(remaining)}  |  "
                        f"완료: {', '.join(submitted) or '없음'}"
                    )
                    alive_remaining = [c for c in remaining if c in alive_crew_set]
                    w_crew = st.selectbox("작업 승무원", alive_remaining or remaining, key=f"work_crew_{sid}")

                    for i, cmd in enumerate(ss["commands"]):
                        cc1, cc2, cc3 = st.columns([3, 2, 1])
                        stat_ko = next((v for v, k in STAT_OPTIONS.items() if k == cmd["stat"]),
                                       list(STAT_OPTIONS.keys())[0])
                        sel = cc1.selectbox("스탯", list(STAT_OPTIONS.keys()),
                                            index=list(STAT_OPTIONS.keys()).index(stat_ko),
                                            key=f"cmd_stat_{sid}_{i}")
                        cnt = cc2.number_input("횟수", 1, 20, cmd["count"],
                                               key=f"cmd_cnt_{sid}_{i}")
                        ss["commands"][i] = {"stat": STAT_OPTIONS[sel], "count": int(cnt)}
                        if cc3.button("삭제", key=f"cmd_del_{sid}_{i}") and len(ss["commands"]) > 1:
                            ss["commands"].pop(i)
                            st.rerun()

                    if st.button("+ 명령 추가", key=f"btn_add_cmd_{sid}"):
                        ss["commands"].append({"stat": "health", "count": 1})
                        st.rerun()

                    if st.button("작업 실행", type="primary", key=f"btn_exec_{sid}"):
                        s2, d2 = api("post", f"/works/sessions/{sid}/main-work", json={
                            "crew_id":  crew_map[w_crew],
                            "commands": ss["commands"],
                        })
                        if s2 == 200:
                            _add_result(ss, _fmt_main_work(w_crew, dmg_type, d2))
                            for block in d2.get("summary", []):
                                if block and block.startswith("["):
                                    turns = block[block.index("]") + 2:].split(" / ")
                                    ok = sum(1 for t in turns if ": 성공" in t)
                                    ss["totals"]["planned"] += len(turns)
                                    ss["totals"]["success"] += ok
                            ss["submitted"].append(w_crew)
                            ss["commands"] = [{"stat": "health", "count": 1}]

                            new_remaining = [c for c in session_crews if c not in ss["submitted"]]
                            new_status    = d2.get("session_status", sess_status)
                            ss["sess_status"] = new_status

                            if new_status == "resolved" or not new_remaining:
                                t = ss["totals"]
                                final_res  = d2.get("session_result") or ""
                                final_text = (
                                    f"■ 최종 작업 결과\n"
                                    f"총 턴수: {t['planned']}  |  "
                                    f"성공: {t['success']}  |  실패: {t['planned'] - t['success']}\n"
                                    f"최종: {final_res}"
                                )
                                _add_result(ss, final_text)
                                ss["resolved"] = True
                            st.rerun()
                        else:
                            st.error(d2)

            elif is_resolved:
                st.success("세션이 종료되었습니다.")

            st.divider()

            # ── ③ 강제 처리 ───────────────────────────────────────────────
            if not is_resolved:
                st.subheader("③ 강제 처리")
                fc1, fc2 = st.columns(2)
                if fc1.button("전체 성공으로 종료", type="primary", key=f"btn_force_ok_{sid}"):
                    s2, d2 = api("post", f"/works/sessions/{sid}/force-complete",
                                 json={"result": "success"})
                    if s2 == 200:
                        _add_result(ss,
                            f"■ 강제 성공 처리\n전체 {d2['total_turns']}턴 성공 기록\n"
                            f"관측률: {d2.get('cargo_observation_rate', 0):.0f}%")
                        ss["resolved"] = True
                        st.rerun()
                    else:
                        st.error(d2)
                if fc2.button("전체 실패로 종료", key=f"btn_force_fail_{sid}"):
                    s2, d2 = api("post", f"/works/sessions/{sid}/force-complete",
                                 json={"result": "fail"})
                    if s2 == 200:
                        _add_result(ss, f"■ 강제 실패 처리\n전체 {d2['total_turns']}턴 실패 기록")
                        ss["resolved"] = True
                        st.rerun()
                    else:
                        st.error(d2)


# ══════════════════════════════════════════════════════════════════════════════
# 화물 재격리
# ══════════════════════════════════════════════════════════════════════════════
with tab_ri:
    ri_sid = st.session_state.ri_sid

    if not ri_sid:
        for i, r in enumerate(st.session_state.ri_results):
            if r["dismissed"]:
                continue
            with st.container(border=True):
                st.code(r["text"], language=None)
                if st.button("닫기", key=f"rip_close_{i}"):
                    st.session_state.ri_results[i]["dismissed"] = True
                    st.rerun()

        st.subheader("재격리 세션 시작")
        if not escaped_map:
            st.info("탈출 상태인 화물이 없습니다.")
        else:
            ri_cargo   = st.selectbox("탈출한 화물", list(escaped_map.keys()), key="ri_cargo")
            ri_crews   = st.multiselect("참여 승무원", list(crew_map.keys()), key="ri_crews")
            cargo_d    = cargo_by_id.get(escaped_map[ri_cargo], {})
            if cargo_d:
                _GRADE_HP     = {"standard": 100, "non_standard": 230, "overload": 330, "fixed": 500}
                _GRADE_WEIGHT = {"standard": 5,   "non_standard": 15,  "overload": 30,  "fixed": 50}
                grade     = cargo_d.get("grade", "standard")
                threshold = int((cargo_d.get("cause", 10) or 10) * 1.2) + _GRADE_WEIGHT.get(grade, 5)
                st.caption(
                    f"등급: {grade}  |  재격리 HP: {_GRADE_HP.get(grade, 100)}"
                    f"  |  명중 임계치: {threshold}"
                )
            if st.button("재격리 세션 시작", type="primary", key="btn_ri_start"):
                s, d = api("post", "/reisolation/sessions", json={
                    "cargo_id": escaped_map[ri_cargo],
                    "crew_ids": [crew_map[c] for c in ri_crews],
                })
                if s in (200, 201):
                    st.session_state.ri_sid           = d["session_id"]
                    st.session_state.ri_cargo_id      = escaped_map[ri_cargo]
                    st.session_state.ri_session_crews = ri_crews
                    st.session_state.ri_results       = []
                    st.rerun()
                else:
                    st.error(d)

    else:
        ri_cargo_id   = st.session_state.get("ri_cargo_id", "")
        ri_cargo_info = cargo_by_id.get(ri_cargo_id, {})

        _, ri_sessions = api("get", "/reisolation/sessions")
        ri_sessions = ri_sessions if isinstance(ri_sessions, list) else []
        cur_session = next((s for s in ri_sessions if s["session_id"] == ri_sid), None)

        rc1, rc2 = st.columns([5, 1])
        hp_str = (
            f"HP {cur_session['cargo_current_hp']}/{cur_session['cargo_max_hp']}"
            if cur_session else ""
        )
        rc1.markdown(
            f"**● 재격리 진행 중** &nbsp; `{ri_sid[:8]}…`  |  "
            f"화물: **{ri_cargo_info.get('cargo_name','?')}**  |  {hp_str}"
        )
        if rc2.button("세션 닫기", key="btn_ri_close"):
            st.session_state.ri_sid = None
            st.rerun()

        if cur_session and cur_session["status"] == "resolved":
            st.success("재격리 세션이 종료되었습니다.")
            st.session_state.ri_sid = None
            st.rerun()

        st.divider()

        for i, r in enumerate(st.session_state.ri_results):
            if r["dismissed"]:
                continue
            with st.container(border=True):
                st.code(r["text"], language=None)
                if st.button("닫기", key=f"ri_close_{i}"):
                    st.session_state.ri_results[i]["dismissed"] = True
                    st.rerun()

        # 공격 판정
        st.subheader("① 공격 판정")
        ri_session_crews       = st.session_state.ri_session_crews or list(crew_map.keys())
        alive_ri_session_crews = [c for c in ri_session_crews if c in alive_crew_set]

        atk_crew = st.selectbox("공격 승무원", alive_ri_session_crews or ri_session_crews, key="ri_atk_crew")
        if st.button("공격", type="primary", key="btn_ri_atk"):
            s, d = api("post", f"/reisolation/sessions/{ri_sid}/attack",
                       json={"crew_id": crew_map[atk_crew]})
            if s == 200:
                ok_str = "명중" if d["success"] else "빗나감"
                result_text = (
                    f"{d['crew_name']} (무기: {d['weapon'] or '없음'})\n"
                    f"굴림: ({d['crew_roll']}) + {d['hit_bonus']} = {d['final_roll']}"
                    f" vs {d['threshold']}  →  {ok_str}\n"
                    f"피해: {d['damage_dealt']}  |  화물 HP: {d['cargo_hp']}\n"
                    f"반격: -{d['counter_damage']} ({d['damage_type']})"
                )
                if d.get("counter_kills"):
                    result_text += f"\n반격 사망: {', '.join(d['counter_kills'])}"
                if d.get("session_resolved"):
                    result_text += f"\n\n■ 세션 종료 — {'재격리 성공' if d.get('final_result') == 'success' else '전멸'}"
                st.session_state.ri_results.append({"text": result_text, "dismissed": False})
                if d.get("session_resolved"):
                    st.session_state.ri_sid = None
                st.rerun()
            else:
                st.error(d)

        st.divider()

        # 패턴 이벤트
        st.subheader("② 패턴 이벤트")
        _, ri_patterns = api("get", f"/reisolation/cargo/{ri_cargo_id}/patterns")
        ri_patterns    = ri_patterns if isinstance(ri_patterns, list) else []
        ri_pattern_map = {p["pattern_name"]: p["pattern_id"] for p in ri_patterns}

        if not ri_pattern_map:
            st.caption("해당 화물에 등록된 재격리 패턴 없음")
        else:
            pe_pattern  = st.selectbox("패턴 선택", list(ri_pattern_map.keys()), key="ri_pe_pattern")
            pe_info     = next((p for p in ri_patterns if p["pattern_name"] == pe_pattern), {})
            if pe_info.get("description"):
                st.caption(pe_info["description"])

            pe_crews    = st.multiselect("대상 승무원", alive_ri_session_crews or ri_session_crews, key="ri_pe_crews")
            pe_use_stat = st.checkbox("주사위 판정 사용", key="ri_pe_use_stat")
            pe_stat     = None
            if pe_use_stat:
                pe_stat_lbl = st.selectbox("판정 스탯", list(STAT_OPTIONS.keys()), key="ri_pe_stat")
                pe_stat     = STAT_OPTIONS[pe_stat_lbl]

            pe_use_resp = st.checkbox("대응지문 판정 사용", key="ri_pe_use_resp")
            pe_response = None
            if pe_use_resp:
                pe_resp_val = st.radio("대응지문 결과", ["성공", "실패"], horizontal=True, key="ri_pe_resp")
                pe_response = pe_resp_val == "성공"

            if st.button("패턴 적용", type="primary", key="btn_ri_pe"):
                s, d = api(
                    "post",
                    f"/reisolation/cargo/{ri_cargo_id}/pattern/{ri_pattern_map[pe_pattern]}",
                    json={
                        "session_id":       ri_sid,
                        "crew_ids":         [crew_map[c] for c in pe_crews],
                        "stat":             pe_stat,
                        "response_success": pe_response,
                    },
                )
                if s == 200:
                    st.session_state.ri_results.append({"text": d.get("log_text", ""), "dismissed": False})
                    if d.get("resolved"):
                        st.session_state.ri_sid = None
                    st.rerun()
                else:
                    st.error(d)


# ══════════════════════════════════════════════════════════════════════════════
# 승무원 즉시 조치
# ══════════════════════════════════════════════════════════════════════════════
with tab_crew:
    if not crew_map:
        st.warning("등록된 승무원이 없습니다.")
    else:
        tc_crew = st.selectbox("승무원 선택", list(crew_map.keys()), key="tc_crew")
        tc_crew_id = crew_map[tc_crew]

        st.divider()

        # ── 즉사 ─────────────────────────────────────────────────────────────
        st.subheader("즉사")
        if st.button("즉사 처리", type="primary", key="btn_tc_kill"):
            s, d = api("post", f"/runners/crew/{tc_crew_id}/kill")
            if s == 200:
                st.success(f"{tc_crew} — 즉사 처리 완료")
            else:
                st.error(d)

        st.divider()

        # ── 즉각 데미지 ───────────────────────────────────────────────────────
        st.subheader("즉각 데미지")
        dc1, dc2 = st.columns(2)
        hp_dmg = dc1.number_input("HP 데미지", min_value=0, value=0, key="tc_hp_dmg")
        sp_dmg = dc2.number_input("SP 데미지", min_value=0, value=0, key="tc_sp_dmg")
        tc_note = st.text_input("사유 (선택)", key="tc_dmg_note")

        if st.button("데미지 적용", key="btn_tc_dmg"):
            if hp_dmg == 0 and sp_dmg == 0:
                st.warning("데미지를 입력해주세요.")
            else:
                s, d = api("patch", f"/runners/crew/{tc_crew_id}/hp-sp", json={
                    "hp_delta": -int(hp_dmg),
                    "sp_delta": -int(sp_dmg),
                    "note":     tc_note or None,
                })
                if s == 200:
                    lines = [f"{tc_crew}"]
                    if hp_dmg: lines.append(f"HP -{hp_dmg} → 잔여 {d.get('hp', '?')}")
                    if sp_dmg: lines.append(f"SP -{sp_dmg} → 잔여 {d.get('sp', '?')}")
                    st.success("  |  ".join(lines))
                else:
                    st.error(d)

        st.divider()

        # ── HP / SP 직접 설정 ─────────────────────────────────────────────────
        st.subheader("HP / SP 직접 회복")
        rc1, rc2 = st.columns(2)
        hp_rec = rc1.number_input("HP 회복량", min_value=0, value=0, key="tc_hp_rec")
        sp_rec = rc2.number_input("SP 회복량", min_value=0, value=0, key="tc_sp_rec")

        if st.button("회복 적용", key="btn_tc_rec"):
            if hp_rec == 0 and sp_rec == 0:
                st.warning("회복량을 입력해주세요.")
            else:
                s, d = api("patch", f"/runners/crew/{tc_crew_id}/hp-sp", json={
                    "hp_delta": int(hp_rec),
                    "sp_delta": int(sp_rec),
                    "note":     "회복 (관리자)",
                })
                if s == 200:
                    lines = [f"{tc_crew}"]
                    if hp_rec: lines.append(f"HP +{hp_rec} → 잔여 {d.get('hp', '?')}")
                    if sp_rec: lines.append(f"SP +{sp_rec} → 잔여 {d.get('sp', '?')}")
                    st.success("  |  ".join(lines))
                else:
                    st.error(d)
