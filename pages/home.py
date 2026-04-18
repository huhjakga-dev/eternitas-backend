import streamlit as st
from registration_dashboard import get_db, fetch_crews, fetch_cargos, GRADE_LABEL, CREW_TYPE_LABEL, MECH

def show():
    st.image("eternitas_banner.png", use_container_width=True)
    st.title("ETERNITAS — 프로필 접수 현황")

    if st.button("새로고침"):
        st.cache_resource.clear()
        st.rerun()

    db = get_db()
    try:
        crews  = fetch_crews(db)
        cargos = fetch_cargos(db)
    except Exception as e:
        st.error(f"DB 오류: {e}")
        return
    finally:
        db.close()

    volunteers = [c for c in crews if c.crew_type == "volunteer"]
    convicts   = [c for c in crews if c.crew_type == "convict"]

    # ── 접수 현황 ──────────────────────────────────────────────────────────────
    st.subheader("접수 현황")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("자원 승무원",   len(volunteers))
    c2.metric("사형수 승무원", len(convicts))
    c3.metric("화물",          len(cargos))
    c4.metric("전체",          len(crews) + len(cargos))

    st.divider()

    # ── 화물 등급 분포 ─────────────────────────────────────────────────────────
    st.subheader("화물 등급 분포")
    grade_order = ["standard", "non_standard", "overload", "fixed"]
    grade_counts = {k: 0 for k in grade_order}
    for c in cargos:
        if c.grade in grade_counts:
            grade_counts[c.grade] += 1
    present = [(k, v) for k, v in grade_counts.items() if v > 0]
    if present:
        g_cols = st.columns(len(present))
        for i, (grade, count) in enumerate(present):
            g_cols[i].metric(GRADE_LABEL.get(grade, grade), count)
    else:
        st.info("접수된 화물 프로필이 없습니다.")

    st.divider()

    # ── 승무원 스탯 분포 ───────────────────────────────────────────────────────
    st.subheader("승무원 스탯 분포")
    if crews:
        stats  = ["health", "mentality", "strength", "inteligence", "luckiness"]
        labels = ["체력", "정신력", "근력", "지력", "행운"]

        for stat, label in zip(stats, labels):
            vals = [getattr(c, stat) or 0 for c in crews]
            low  = sum(1 for v in vals if 1 <= v <= 4)
            mid  = sum(1 for v in vals if 5 <= v <= 7)
            high = sum(1 for v in vals if 8 <= v <= 10)
            st.caption(label)
            s1, s2, s3 = st.columns(3)
            s1.metric("1 ~ 4", low)
            s2.metric("5 ~ 7", mid)
            s3.metric("8 ~ 10", high)

        # ── 기계화 단계 분포 ───────────────────────────────────────────────────
        st.subheader("기계화 단계 분포")
        mech_counts = {}
        for c in crews:
            lv = MECH.get(c.mechanization_lv or 0, "—")
            mech_counts[lv] = mech_counts.get(lv, 0) + 1
        m_cols = st.columns(max(len(mech_counts), 1))
        for i, (lv, count) in enumerate(sorted(mech_counts.items())):
            m_cols[i].metric(lv, count)
    else:
        st.info("접수된 승무원 프로필이 없습니다.")
        st.divider()
show()
