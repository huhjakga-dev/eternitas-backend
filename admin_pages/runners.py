import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("러너 등록")

runner_type = st.radio("유형", ["승무원", "화물"], horizontal=True)

if runner_type == "승무원":
    crew_name = st.text_input("이름", key="crew_name")
    crew_type = st.radio("유형", ["자원", "사형수"], horizontal=True, key="crew_type")

    c1, c2, c3, c4, c5 = st.columns(5)
    health      = c1.number_input("체력",   1, 10, 1, key="r_health")
    strength    = c3.number_input("근력",   1, 10, 1, key="r_strength")
    mentality   = c2.number_input("정신력", 1, 10, 1, key="r_mentality")
    inteligence = c4.number_input("지력",   1, 10, 1, key="r_int")
    luckiness   = c5.number_input("행운",   1, 10, 1, key="r_luck")
    st.caption(f"스탯 합계: {health + mentality + strength + inteligence + luckiness} / 25")
    mech_lv = st.number_input("기계화 단계", 0, 4, 0, key="r_mech")

    if st.button("승무원 등록"):
        status, data = api("post", "/runners/crew", json={
            "crew_name":        crew_name,
            "crew_type":        "volunteer" if crew_type == "자원" else "convict",
            "health":           health, "mentality": mentality,
            "strength":         strength, "inteligence": inteligence,
            "luckiness":        luckiness,
            "mechanization_lv": mech_lv,
        })
        if status in (200, 201):
            st.success(data)
        else:
            st.error(data)

else:
    cargo_code = st.text_input("화물 코드 (공개용)", key="cargo_code")
    cargo_name = st.text_input("화물 이름 (관측 후 공개)", key="cargo_name")
    _GRADE  = {"규격": "standard", "비규격": "non_standard", "과적": "overload", "고착": "fixed"}
    _DAMAGE = {"HP (체력)": "hp", "SP (정신력)": "sp", "둘 다": "both"}
    grade       = _GRADE[st.selectbox("위험 등급", list(_GRADE.keys()), key="cargo_grade")]
    damage_type = _DAMAGE[st.selectbox("데미지 유형", list(_DAMAGE.keys()), key="cargo_damage_type")]

    c1, c2, c3, c4, c5 = st.columns(5)
    health      = c1.number_input("체력",   10, 50, 10, key="rc_health")
    strength    = c3.number_input("근력",   10, 50, 10, key="rc_strength")
    mentality   = c2.number_input("정신력", 10, 50, 10, key="rc_mentality")
    inteligence = c4.number_input("지력",   10, 50, 10, key="rc_int")
    cause       = c5.number_input("인과",   10, 50, 10, key="rc_cause")
    st.caption(f"스탯 합계: {health + mentality + strength + inteligence + cause}")

    if st.button("화물 등록"):
        status, data = api("post", "/runners/cargo", json={
            "cargo_name":  cargo_name,
            "cargo_code":  cargo_code or None,
            "grade":       grade,
            "damage_type": damage_type,
            "health":      health, "mentality": mentality,
            "strength":    strength, "inteligence": inteligence,
            "cause":       cause,
        })
        if status in (200, 201):
            st.success(data)
        else:
            st.error(data)
