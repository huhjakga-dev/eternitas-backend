import streamlit as st
from admin_pages.admin_api import api

st.image("eternitas_banner.png", use_container_width=True)
st.title("화물 전조 패턴 등록")

cargo_id = st.text_input("cargo_id (화물 생성시 뜨는거 복붙)", key="pattern_cargo_id")
pattern_name = st.text_input("패턴 이름", key="pattern_name")
description = st.text_area("전조 현상 설명 (작업 때 나올 내용)", key="pattern_desc")
answer = st.text_area("전조 현상에 대한 정답", key="pattern_answer")

st.markdown("**버프 (성공 시, 양수로 입력)**")
bc1, bc2, bc3, bc4, bc5 = st.columns(5)
buff_hp   = bc1.number_input("체력 버프",   value=0.0, step=0.1, key="buff_hp")
buff_sp   = bc2.number_input("정신력 버프", value=0.0, step=0.1, key="buff_sp")
buff_str  = bc3.number_input("근력 버프",   value=0.0, step=0.1, key="buff_str")
buff_int  = bc4.number_input("지력 버프",   value=0.0, step=0.1, key="buff_int")
buff_luck = bc5.number_input("행운 버프",   value=0.0, step=0.1, key="buff_luck")
buff_dmg_red = st.number_input("데미지 감소율 (0~1, 양수로 입력)", 0.0, 1.0, 0.0, step=0.05, key="buff_dmg_red")

st.markdown("**디버프 (실패 시, 음수로 입력)**")
dc1, dc2, dc3, dc4, dc5 = st.columns(5)
debuff_hp   = dc1.number_input("체력 디버프",   value=0.0, step=0.1, key="debuff_hp")
debuff_sp   = dc2.number_input("정신력 디버프", value=0.0, step=0.1, key="debuff_sp")
debuff_str  = dc3.number_input("근력 디버프",   value=0.0, step=0.1, key="debuff_str")
debuff_int  = dc4.number_input("지력 디버프",   value=0.0, step=0.1, key="debuff_int")
debuff_luck = dc5.number_input("행운 디버프",   value=0.0, step=0.1, key="debuff_luck")
debuff_dmg_inc = st.number_input("데미지 증가율 (0~1, 양수로 입력)", 0.0, 1.0, 0.0, step=0.05, key="debuff_dmg_inc")
instant_kill = st.number_input("대실패 즉사 확률 (0~1)", 0.0, 1.0, 0.0, step=0.05, key="instant_kill")

if st.button("패턴 등록/수정"):
    status, data = api("post", "/runners/cargo/pattern", json={
        "cargo_id": cargo_id, "pattern_name": pattern_name,
        "description": description, "answer": answer,
        "buff_stat_json": {"health": buff_hp, "mentality": buff_sp, "strength": buff_str, "inteligence": buff_int, "luckiness": buff_luck},
        "buff_damage_reduction": buff_dmg_red,
        "debuff_stat_json": {"health": debuff_hp, "mentality": debuff_sp, "strength": debuff_str, "inteligence": debuff_int, "luckiness": debuff_luck},
        "debuff_demage_increase": debuff_dmg_inc,
        "instant_kill_rate": instant_kill if instant_kill > 0 else None,
    })
    if status in (200, 201):
        st.success(data)
    else:
        st.error(data)
