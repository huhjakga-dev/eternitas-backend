import streamlit as st
from registration_dashboard import get_db, fetch_crews, MECH, CREW_TYPE_LABEL

def show():
    st.image("eternitas_banner.png", use_container_width=True)
    st.title("승무원 신청 현황")

    col_r, col_v = st.columns([1, 4])
    with col_r:
        if st.button("새로고침"):
            st.cache_resource.clear()
            st.rerun()
    with col_v:
        view = st.radio("보기 방식", ["카드", "테이블"], horizontal=True)

    db = get_db()
    try:
        crews = fetch_crews(db)
    except Exception as e:
        st.error(f"DB 오류: {e}")
        return
    finally:
        db.close()

    st.metric("신청 인원", len(crews))
    st.divider()

    if not crews:
        st.info("신청된 승무원이 없습니다.")
        return

    if view == "카드":
        for type_key, type_label in [("volunteer", "자원 승무원"), ("convict", "사형수 승무원")]:
            typed = [c for c in crews if c.crew_type == type_key]
            if not typed:
                continue
            st.subheader(f"{type_label} ({len(typed)}명)")
            cols = st.columns(4)
            for idx, c in enumerate(typed):
                total = (c.health or 0) + (c.mentality or 0) + (c.strength or 0) + (c.inteligence or 0) + (c.luckiness or 0)

                def pip(val):
                    return "".join(
                        f'<span style="display:inline-block;width:10px;height:10px;border-radius:2px;'
                        f'margin:1px;background:{"#4ade80" if i < val else "#374151"};"></span>'
                        for i in range(10)
                    )

                with cols[idx % 4]:
                    st.markdown(f"""
<div style="background:#1e293b;border-radius:8px;padding:12px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
    <b style="font-size:1rem;color:#f1f5f9;">{c.crew_name}</b>
    <span style="font-size:0.72rem;color:#94a3b8;">{MECH.get(c.mechanization_lv or 0, "—")}</span>
  </div>
  <div style="font-size:0.72rem;color:#9ca3af;line-height:1.8;">
    체력&nbsp;&nbsp;&nbsp;{pip(c.health or 0)}<br>
    정신력&nbsp;{pip(c.mentality or 0)}<br>
    근력&nbsp;&nbsp;&nbsp;{pip(c.strength or 0)}<br>
    지력&nbsp;&nbsp;&nbsp;{pip(c.inteligence or 0)}<br>
    행운&nbsp;&nbsp;&nbsp;{pip(c.luckiness or 0)}
  </div>
  <div style="text-align:right;font-size:0.72rem;color:#64748b;margin-top:4px;">합계 {total} / 25</div>
</div>
""", unsafe_allow_html=True)

    else:
        import pandas as pd
        rows = [
            {
                "이름":   c.crew_name,
                "유형":   CREW_TYPE_LABEL.get(c.crew_type, c.crew_type),
                "체력":   c.health or 0,
                "정신력": c.mentality or 0,
                "근력":   c.strength or 0,
                "지력":   c.inteligence or 0,
                "행운":   c.luckiness or 0,
                "합계":   (c.health or 0) + (c.mentality or 0) + (c.strength or 0) + (c.inteligence or 0) + (c.luckiness or 0),
                "기계화": MECH.get(c.mechanization_lv or 0, "—"),
            }
            for c in crews
        ]
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "체력":   st.column_config.NumberColumn("체력",   width="small"),
                "정신력": st.column_config.NumberColumn("정신력", width="small"),
                "근력":   st.column_config.NumberColumn("근력",   width="small"),
                "지력":   st.column_config.NumberColumn("지력",   width="small"),
                "행운":   st.column_config.NumberColumn("행운",   width="small"),
                "합계":   st.column_config.NumberColumn("합계",   width="small"),
                "기계화": st.column_config.TextColumn("기계화",  width="small"),
            },
        )

show()
