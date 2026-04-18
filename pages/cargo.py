import streamlit as st
from registration_dashboard import get_db, fetch_cargos, GRADE_LABEL

GRADE_COLOR = {
    "standard":     "#22c55e",
    "non_standard": "#f59e0b",
    "overload":     "#ef4444",
    "fixed":        "#3b82f6",
}

def show():
    st.image("eternitas_banner.png", use_container_width=True)
    st.title("화물 접수 현황")

    col_r, col_v = st.columns([1, 4])
    with col_r:
        if st.button("새로고침"):
            st.cache_resource.clear()
            st.rerun()
    with col_v:
        view = st.radio("보기 방식", ["카드", "테이블"], horizontal=True)

    db = get_db()
    try:
        cargos = fetch_cargos(db)
    except Exception as e:
        st.error(f"DB 오류: {e}")
        return
    finally:
        db.close()

    st.metric("화물 접수", len(cargos))
    st.divider()

    if not cargos:
        st.info("접수된 화물 프로필이 없습니다.")
        return

    if view == "카드":
        cols = st.columns(4)
        for idx, c in enumerate(cargos):
            color = GRADE_COLOR.get(c.grade, "#9ca3af")
            with cols[idx % 4]:
                st.markdown(f"""
<div style="background:#1e293b;border-radius:8px;padding:12px;margin-bottom:8px;">
  <b style="font-size:1rem;color:#f1f5f9;">{c.cargo_code or "미공개"}</b>
  <div style="margin-top:6px;">
    <span style="font-size:0.78rem;color:{color};font-weight:600;">
      {GRADE_LABEL.get(c.grade, c.grade)}
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

    else:
        import pandas as pd
        rows = [
            {
                "화물 코드": c.cargo_code or "미공개",
                "위험 등급": GRADE_LABEL.get(c.grade, c.grade),
            }
            for c in cargos
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

show()
