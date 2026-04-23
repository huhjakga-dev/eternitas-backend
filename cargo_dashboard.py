"""
ETERNITAS 화물 현황 대시보드
실행: streamlit run cargo_dashboard.py
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

def fetch_cargos(db):
    return db.execute(text("""
        SELECT
            c.id::text,
            c.cargo_name,
            c.cargo_code,
            c.grade,
            c.damage_type,
            c.health, c.mentality, c.strength, c.inteligence, c.cause,
            c.observation_rate,
            c.success_count, c.failure_count,
            c.adapt_point,
            c.total_turns,
            c.is_escaped
        FROM cargos c
        ORDER BY c.grade, c.cargo_name
    """)).fetchall()

def fetch_patterns_by_cargo(db, cargo_ids: list[str]):
    if not cargo_ids:
        return {}
    rows = db.execute(text("""
        SELECT
            p.id::text,
            p.cargo_id::text,
            p.pattern_name,
            p.description,
            p.answer,
            p.buff_stat_json,
            p.buff_damage_reduction,
            p.debuff_stat_json,
            p.debuff_demage_increase,
            p.instant_kill
        FROM cargo_patterns p
        WHERE p.cargo_id = ANY(CAST(:ids AS uuid[]))
        ORDER BY p.cargo_id, p.pattern_name
    """), {"ids": cargo_ids}).fetchall()

    result: dict[str, list] = {}
    for r in rows:
        result.setdefault(r.cargo_id, []).append(r)
    return result

# ── 상수 ──────────────────────────────────────────────────────────────────────

GRADE_KR = {
    "standard":     "표준",
    "non_standard": "비표준",
    "overload":     "과적",
    "fixed":        "고착",
}
GRADE_COLOR = {
    "standard":     "#3b82f6",
    "non_standard": "#a855f7",
    "overload":     "#f97316",
    "fixed":        "#ef4444",
}
DAMAGE_KR = {"hp": "HP", "sp": "SP", "both": "HP+SP"}

def _obs_bar_color(rate: float) -> str:
    if rate >= 80: return "#22c55e"
    if rate >= 40: return "#f59e0b"
    return "#64748b"

def _stat_pips(val: float, max_val: int = 50) -> str:
    filled = min(int(val / max_val * 10), 10)
    return "".join(
        f'<span style="display:inline-block;width:11px;height:11px;border-radius:2px;'
        f'margin:1px;background:{"#f87171" if i < filled else "#374151"};"></span>'
        for i in range(10)
    )

def _obs_bar(rate: float) -> str:
    color = _obs_bar_color(rate)
    pct   = max(0, min(100, int(rate)))
    return (
        f'<div style="background:#2a2a2a;border-radius:3px;height:8px;">'
        f'<div style="background:{color};border-radius:3px;height:8px;width:{pct}%;"></div>'
        f'</div><small style="color:#9ca3af">{rate:.1f}%</small>'
    )

def _stat_mods_text(stat_json: dict) -> str:
    if not stat_json:
        return "없음"
    parts = []
    labels = {"health": "체력", "mentality": "정신력", "strength": "근력",
              "inteligence": "지력", "luckiness": "행운"}
    for k, v in stat_json.items():
        if v and k in labels:
            sign = "+" if v > 0 else ""
            parts.append(f"{labels[k]} {sign}{v}")
    return ", ".join(parts) if parts else "없음"

# ── 패턴 렌더링 ───────────────────────────────────────────────────────────────

def render_patterns(patterns: list) -> None:
    if not patterns:
        st.caption("등록된 패턴 없음")
        return
    for p in patterns:
        with st.expander(f"**{p.pattern_name}**" + (" · 즉사" if p.instant_kill else ""), expanded=False):
            st.markdown(f"**설명:** {p.description or '—'}")
            if p.answer:
                st.markdown(f"**정답:** `{p.answer}`")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**버프**")
                st.caption(f"스탯: {_stat_mods_text(p.buff_stat_json)}")
                if p.buff_damage_reduction:
                    st.caption(f"피해 경감: -{p.buff_damage_reduction * 100:.0f}%")
            with c2:
                st.markdown("**디버프**")
                st.caption(f"스탯: {_stat_mods_text(p.debuff_stat_json)}")
                if p.debuff_demage_increase:
                    st.caption(f"피해 증가: +{p.debuff_demage_increase * 100:.0f}%")
            if p.instant_kill:
                st.error("즉사 패턴")

# ── 메인 ──────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="ETERNITAS – 화물 현황",
        page_icon="📦",
        layout="wide",
    )

    st.image("eternitas_banner.png", use_container_width=True)
    st.title("ETERNITAS — 화물 현황판")

    col_r, col_v = st.columns([1, 4])
    with col_r:
        if st.button("새로고침"):
            st.cache_resource.clear()
            st.rerun()
    with col_v:
        view = st.radio("보기 방식", ["테이블", "카드"], horizontal=True)

    db = get_db()
    try:
        cargos      = fetch_cargos(db)
        cargo_ids   = [c.id for c in cargos]
        pattern_map = fetch_patterns_by_cargo(db, cargo_ids)
    except Exception as e:
        st.error(f"DB 오류: {e}")
        return
    finally:
        db.close()

    if not cargos:
        st.info("표시할 화물이 없습니다.")
        return

    # ── 테이블 뷰 ────────────────────────────────────────────────────────────
    if view == "테이블":
        import pandas as pd

        rows = []
        for c in cargos:
            grade    = c.grade or ""
            obs      = c.observation_rate or 0.0
            revealed = obs > 20
            rows.append({
                "화물코드":  c.cargo_code or "—",
                "이름":      c.cargo_name if revealed else "비공개",
                "등급":      GRADE_KR.get(grade, grade),
                "피해 유형": DAMAGE_KR.get(c.damage_type or "hp", c.damage_type or "—"),
                "관측률":    obs / 100,
                "관측률 수치": f"{obs:.1f}%",
                "체력":      c.health or 0,
                "정신력":    c.mentality or 0,
                "근력":      c.strength or 0,
                "지력":      c.inteligence or 0,
                "원인력":    c.cause or 0,
                "총 턴":     c.total_turns or 0,
                "탈출":      "탈출 중" if c.is_escaped else "수용 중",
            })

        df = pd.DataFrame(rows)

        def _highlight_escaped(row):
            if row["탈출"] == "탈출 중":
                return ["background-color: #3b1a0a; color: #fdba74;"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df.style.apply(_highlight_escaped, axis=1),
            use_container_width=True,
            hide_index=True,
            column_config={
                "관측률": st.column_config.ProgressColumn(
                    "관측률", min_value=0, max_value=1, format=" ",
                ),
                "관측률 수치": st.column_config.TextColumn("관측률 수치", width="small"),
                "화물코드":  st.column_config.TextColumn("화물코드",  width="small"),
                "이름":      st.column_config.TextColumn("이름",      width="medium"),
                "등급":      st.column_config.TextColumn("등급",      width="small"),
                "피해 유형": st.column_config.TextColumn("피해 유형", width="small"),
                "체력":      st.column_config.NumberColumn("체력",    width="small"),
                "정신력":    st.column_config.NumberColumn("정신력",  width="small"),
                "근력":      st.column_config.NumberColumn("근력",    width="small"),
                "지력":      st.column_config.NumberColumn("지력",    width="small"),
                "원인력":    st.column_config.NumberColumn("원인력",  width="small"),
                "총 턴":     st.column_config.NumberColumn("총 턴",   width="small"),
                "탈출":      st.column_config.TextColumn("탈출",      width="small"),
            },
            height=min(80 + len(rows) * 35, 700),
        )

        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("전체 화물",  len(cargos))
        m2.metric("탈출 중",    sum(1 for c in cargos if c.is_escaped))
        m3.metric("수용 중",    sum(1 for c in cargos if not c.is_escaped))
        m4.metric("관측 완료",  sum(1 for c in cargos if (c.observation_rate or 0) >= 100))

        # 패턴 확인 섹션
        st.divider()
        st.subheader("패턴 조회")
        revealed_cargos = [c for c in cargos if (c.observation_rate or 0) > 20]
        if not revealed_cargos:
            st.caption("관측률 20% 초과 화물이 없습니다.")
        else:
            selected = st.selectbox(
                "화물 선택",
                options=revealed_cargos,
                format_func=lambda c: f"[{GRADE_KR.get(c.grade, c.grade)}] {c.cargo_name}",
            )
            if selected:
                render_patterns(pattern_map.get(selected.id, []))

    # ── 카드 뷰 ──────────────────────────────────────────────────────────────
    else:
        cols = st.columns(3)
        for idx, c in enumerate(cargos):
            grade    = c.grade or ""
            obs      = c.observation_rate or 0.0
            revealed = obs > 20
            g_color  = GRADE_COLOR.get(grade, "#64748b")
            card_bg  = "#3b1a0a" if c.is_escaped else "#1e293b"

            display_name = c.cargo_name if revealed else "비공개"
            display_code = c.cargo_code or "—"

            stat_rows = (
                f'체력 {_stat_pips(c.health or 0)}<br>'
                f'정신력 {_stat_pips(c.mentality or 0)}<br>'
                f'근력 {_stat_pips(c.strength or 0)}<br>'
                f'지력 {_stat_pips(c.inteligence or 0)}<br>'
                f'원인력 {_stat_pips(c.cause or 0)}'
            )

            escaped_badge = (
                '<span style="color:#fb923c;font-size:0.72rem;font-weight:bold;">탈출 중</span>'
                if c.is_escaped else
                '<span style="color:#4ade80;font-size:0.72rem;">수용 중</span>'
            )

            with cols[idx % 3]:
                st.markdown(f"""
<div style="background:{card_bg};border-radius:8px;padding:12px;margin-bottom:4px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
    <b style="font-size:1rem;color:#f1f5f9;">{display_name}</b>
    {escaped_badge}
  </div>
  <div style="display:flex;justify-content:space-between;font-size:0.72rem;margin-bottom:8px;">
    <span style="color:#94a3b8;">코드 {display_code}</span>
    <span style="color:{g_color};font-weight:bold;">{GRADE_KR.get(grade, grade)}</span>
  </div>
  <div style="margin-bottom:6px;">
    {_obs_bar(obs)}
  </div>
  <div style="font-size:0.72rem;color:#9ca3af;margin-top:8px;">
    {stat_rows}
  </div>
</div>
""", unsafe_allow_html=True)

                # 패턴 버튼 (카드 바로 아래)
                patterns = pattern_map.get(c.id, [])
                if patterns:
                    with st.expander(f"패턴 {len(patterns)}개 보기"):
                        render_patterns(patterns)
                else:
                    st.caption("패턴 없음")

                st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
