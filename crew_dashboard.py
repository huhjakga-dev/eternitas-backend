"""
ETERNITAS 승무원 상태 대시보드
실행: streamlit run crew_dashboard.py
"""
import os
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

HOST     = os.getenv("host")
PORT     = os.getenv("port", "5432")
USER     = os.getenv("user")
PASSWORD = os.getenv("password")
DBNAME   = os.getenv("dbname")

DATABASE_URL = (
    f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
)

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

def get_db():
    return sessionmaker(bind=get_engine())()

# ── 데이터 ────────────────────────────────────────────────────────────────────

def fetch_crews(db):
    return db.execute(text("""
        SELECT
            c.id::text,
            c.crew_name,
            c.health, c.mentality, c.strength, c.inteligence, c.luckiness,
            c.mechanization_lv,
            c.hp, c.sp,
            c.max_hp, c.max_sp,
            c.token,
            c.is_dead, c.is_active,
            c.death_time AS death_time_utc
        FROM crews c
        ORDER BY c.crew_name
    """)).fetchall()

def fetch_status_effects_by_crew(db, crew_ids: list[str]):
    if not crew_ids:
        return {}
    rows = db.execute(text("""
        SELECT cse.crew_id::text, se.name
        FROM crew_status_effects cse
        JOIN status_effects se ON se.id = cse.status_effect_id
        WHERE cse.crew_id = ANY(CAST(:ids AS uuid[]))
    """), {"ids": crew_ids}).fetchall()
    result: dict[str, list] = {}
    for crew_id, name in rows:
        result.setdefault(crew_id, []).append(name)
    return result


def fetch_equipments_by_crew(db, crew_ids: list[str]):
    if not crew_ids:
        return {}
    rows = db.execute(text("""
        SELECT
            ce.crew_id::text,
            e.name,
            e.equipment_type,
            ce.is_equipped
        FROM crew_equipments ce
        JOIN equipments e ON e.id = ce.equipment_id
        WHERE ce.crew_id = ANY(CAST(:ids AS uuid[]))
        ORDER BY ce.crew_id, ce.is_equipped DESC
    """), {"ids": crew_ids}).fetchall()

    result: dict[str, list] = {}
    for r in rows:
        result.setdefault(r.crew_id, []).append(r)
    return result

# ── 상수 ──────────────────────────────────────────────────────────────────────

MECH = {0: "Lv.0", 1: "Lv.1", 2: "Lv.2", 3: "Lv.3", 4: "Lv.4"}

def status_label(is_dead, is_active, has_se=False):
    if is_dead:       return "사망"
    if has_se:        return "상태이상"
    if not is_active: return "비활성"
    return "활성"

# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="ETERNITAS – 승무원 현황",
        page_icon="🚂",
        layout="wide",
    )

    st.image("eternitas_banner.png", use_container_width=True)
    st.title("ETERNITAS — 승무원 현황판")

    col_r, col_v = st.columns([1, 4])
    with col_r:
        if st.button("새로고침"):
            st.cache_resource.clear()
            st.rerun()
    with col_v:
        view = st.radio("보기 방식", ["테이블", "카드"], horizontal=True)

    db = get_db()
    try:
        crews = fetch_crews(db)
        crew_ids = [c.id for c in crews]
        eq_map = fetch_equipments_by_crew(db, crew_ids)
        se_map = fetch_status_effects_by_crew(db, crew_ids)
    except Exception as e:
        st.error(f"DB 오류: {e}")
        return
    finally:
        db.close()

    visible = crews
    if not visible:
        st.info("표시할 승무원이 없습니다.")
        return

    # ── 테이블 뷰 ────────────────────────────────────────────────────────────
    if view == "테이블":
        import pandas as pd

        from datetime import timedelta

        rows = []
        for c in visible:
            max_hp   = c.max_hp or 1
            max_sp   = c.max_sp or 1
            eqs      = eq_map.get(c.id, [])
            effects  = se_map.get(c.id, [])
            eq_str   = ", ".join(
                f"{'[착용]' if e.is_equipped else '[미착용]'}{e.name}"
                for e in eqs
            ) or "—"
            death_kst  = c.death_time_utc + timedelta(hours=9) if c.death_time_utc else None
            death_str  = death_kst.strftime("%H:%M")                          if death_kst else "—"
            revive_str = (death_kst + timedelta(hours=1)).strftime("%H:%M")   if death_kst else "—"
            rows.append({
                "이름":       c.crew_name,
                "상태":       status_label(c.is_dead, c.is_active, bool(effects)),
                "상태이상":   ", ".join(effects) if effects else "—",
                "HP":         (c.hp or 0) / max_hp,
                "HP 수치":    f"{c.hp or 0}/{max_hp}",
                "SP":         (c.sp or 0) / max_sp,
                "SP 수치":    f"{c.sp or 0}/{max_sp}",
                "체력":       c.health or 0,
                "정신력":     c.mentality or 0,
                "근력":       c.strength or 0,
                "지력":       c.inteligence or 0,
                "행운":       c.luckiness or 0,
                "기계화":     MECH.get(c.mechanization_lv or 0, "—"),
                "토큰":       c.token or 0,
                "장비":       eq_str,
                "사망 시각":  death_str,
                "부활 시각":  revive_str,
            })

        df = pd.DataFrame(rows)

        def _highlight_dead(row):
            if row["상태"] == "사망":
                return ["background-color: #3b0a0a; color: #fca5a5;"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(_highlight_dead, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "HP": st.column_config.ProgressColumn(
                    "HP", min_value=0, max_value=1, format=" ",
                ),
                "SP": st.column_config.ProgressColumn(
                    "SP", min_value=0, max_value=1, format=" ",
                ),
                "HP 수치":  st.column_config.TextColumn("HP 수치",  width="small"),
                "SP 수치":  st.column_config.TextColumn("SP 수치",  width="small"),
                "체력":     st.column_config.NumberColumn("체력",   width="small"),
                "정신력":   st.column_config.NumberColumn("정신력", width="small"),
                "근력":     st.column_config.NumberColumn("근력",   width="small"),
                "지력":     st.column_config.NumberColumn("지력",   width="small"),
                "행운":     st.column_config.NumberColumn("행운",   width="small"),
                "기계화":   st.column_config.TextColumn("기계화",  width="small"),
                "토큰":     st.column_config.NumberColumn("토큰",   width="small"),
                "상태이상": st.column_config.TextColumn("상태이상",  width="medium"),
                "장비":     st.column_config.TextColumn("장비",      width="medium"),
                "사망 시각":st.column_config.TextColumn("사망 시각", width="small"),
                "부활 시각":st.column_config.TextColumn("부활 시각", width="small"),
            },
            height=min(80 + len(rows) * 35, 700),
        )

        # 요약 지표
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("전체 승무원",    len(crews))
        m2.metric("활성",           sum(1 for c in crews if not c.is_dead and not se_map.get(c.id)))
        m3.metric("상태이상 적용",  sum(1 for c in crews if not c.is_dead and se_map.get(c.id)))
        m4.metric("사망",           sum(1 for c in crews if c.is_dead))

    # ── 카드 뷰 ──────────────────────────────────────────────────────────────
    else:
        def bar(cur, mx, color):
            pct = max(0, min(100, int(cur / mx * 100))) if mx else 0
            return (
                f'<div style="background:#2a2a2a;border-radius:3px;height:10px;">'
                f'<div style="background:{color};border-radius:3px;height:10px;width:{pct}%;"></div>'
                f'</div><small style="color:#9ca3af">{cur}/{mx}</small>'
            )

        def pip(val):
            return "".join(
                f'<span style="display:inline-block;width:11px;height:11px;border-radius:2px;'
                f'margin:1px;background:{"#FBBF24" if i < val else "#374151"};"></span>'
                for i in range(10)
            )

        from datetime import timedelta

        cols = st.columns(4)
        for idx, c in enumerate(visible):
            max_hp      = c.max_hp or 1
            max_sp      = c.max_sp or 1
            eqs         = eq_map.get(c.id, [])
            effects     = se_map.get(c.id, [])
            has_se      = bool(effects)
            badge_color = "#ef4444" if c.is_dead else ("#a855f7" if has_se else ("#6b7280" if not c.is_active else "#22c55e"))
            card_bg     = "#3b0a0a" if c.is_dead else ("#1e1b2e" if has_se else "#1e293b")
            divider_color = "#6b2020" if c.is_dead else "#334155"

            death_kst   = c.death_time_utc + timedelta(hours=9) if c.death_time_utc else None
            death_block = ""
            if c.is_dead and death_kst:
                revive = (death_kst + timedelta(hours=1)).strftime("%H:%M")
                death_block = (
                    f'<div style="margin-top:6px;font-size:0.72rem;color:#fca5a5;">'
                    f'사망 {death_kst.strftime("%H:%M")} → 부활 {revive}'
                    f'</div>'
                )

            def eq_item(e):
                label = "[착용]" if e.is_equipped else "[미착용]"
                type_tag = (
                    '  <code style="font-size:0.7rem">' + e.equipment_type + "</code>"
                    if e.equipment_type else ""
                )
                return '<div style="font-size:0.75rem;color:#e2e8f0;">' + label + " " + e.name + type_tag + "</div>"

            eq_html = "".join(eq_item(e) for e in eqs) or '<div style="font-size:0.75rem;color:#6b7280;">장비 없음</div>'

            with cols[idx % 4]:
                st.markdown(f"""
<div style="background:{card_bg};border-radius:8px;padding:12px;margin-bottom:8px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <b style="font-size:1rem;color:#f1f5f9;">{c.crew_name}</b>
    <span style="font-size:0.72rem;color:{badge_color};">{status_label(c.is_dead, c.is_active, has_se)}</span>
  </div>
  {''.join(f'<span style="background:#6d28d9;color:#e9d5ff;font-size:0.65rem;padding:1px 7px;border-radius:10px;margin:1px;">{e}</span>' for e in effects) + ('<br>' if effects else '')}
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#64748b;margin-bottom:8px;">
    <span>기계화 {MECH.get(c.mechanization_lv or 0, '—')}</span>
    <span style="color:#ffb716;">토큰 {c.token or 0}</span>
  </div>
  {death_block}
  {bar(c.hp or 0, max_hp, '#FBBF24')}
  {bar(c.sp or 0, max_sp, '#FDE047')}
  <div style="margin-top:8px;font-size:0.72rem;color:#9ca3af;">
    체력 {pip(c.health or 0)}<br>
    정신력 {pip(c.mentality or 0)}<br>
    근력 {pip(c.strength or 0)}<br>
    지력 {pip(c.inteligence or 0)}<br>
    행운 {pip(c.luckiness or 0)}
  </div>
  <div style="margin-top:8px;border-top:1px solid {divider_color};padding-top:6px;">
    {eq_html}
  </div>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
