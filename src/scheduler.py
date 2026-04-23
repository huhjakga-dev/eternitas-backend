from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database import SessionLocal
from src.runners.models import Crew
from src.works.models import WorkSession
from src.train.models import TrainState
from src.common.schema import WorkStatus
from src.common.utils import compute_max_caps

_SEOUL = ZoneInfo("Asia/Seoul")

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


async def scheduled_resurrect():
    """사망 후 1시간 경과한 승무원 부활: HP 풀 회복, 기계화 단계 +1, is_dead=False"""
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(hours=1)
        dead_crews = (
            db.query(Crew)
            .filter(Crew.is_dead == True, Crew.death_time <= threshold)
            .all()
        )
        for crew in dead_crews:
            crew.is_dead    = False
            crew.death_time = None
            crew.mechanization_lv = min((crew.mechanization_lv or 0) + 1, 4)
            max_hp, max_sp = compute_max_caps(
                crew.health, crew.mentality,
                crew.mechanization_lv, crew.initial_mechanization_lv or 0,
            )
            crew.max_hp = max_hp
            crew.max_sp = max_sp
            crew.hp     = max_hp
            crew.sp     = max_sp
        if dead_crews:
            db.commit()
    finally:
        db.close()


async def scheduled_midnight_recovery():
    """매일 자정 살아있는 승무원 HP/SP 회복.
    50% 초과 잔여: +10 / 50% 이하: +10 + (max/2 - current) * 0.6
    """
    db = SessionLocal()
    try:
        crews = db.query(Crew).filter(Crew.is_dead == False).all()
        for crew in crews:
            max_hp = crew.max_hp or (10 + (crew.health or 1) * 5)
            max_sp = crew.max_sp or ((crew.mentality or 1) * 5)
            hp = crew.hp or 0
            sp = crew.sp or 0

            hp_gain = 10 if hp > max_hp // 2 else 10 + int((max_hp / 2 - hp) * 0.6)
            sp_gain = 10 if sp > max_sp // 2 else 10 + int((max_sp / 2 - sp) * 0.6)

            crew.hp = min(max_hp, hp + hp_gain)
            crew.sp = min(max_sp, sp + sp_gain)

        if crews:
            db.commit()
    finally:
        db.close()


async def scheduled_train_speed():
    """
    매일 12시: 당일 완료된 작업 세션 성공률 계산 → 열차 속력 조정.
    성공률 > 0.75 → +1Mph / 0.25~0.75 → 변화 없음 / < 0.25 → -1Mph
    """
    db = SessionLocal()
    try:
        now         = datetime.now(_SEOUL)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_utc   = today_start.astimezone(timezone.utc).replace(tzinfo=None)
        now_utc     = now.astimezone(timezone.utc).replace(tzinfo=None)

        sessions = (
            db.query(WorkSession)
            .filter(
                WorkSession.status == WorkStatus.RESOLVED,
                WorkSession.final_result.in_(["success", "fail"]),
                WorkSession.updated_at >= today_utc,
                WorkSession.updated_at <= now_utc,
            )
            .all()
        )
        if not sessions:
            return

        total   = len(sessions)
        success = sum(1 for s in sessions if s.final_result == "success")
        ratio   = success / total

        state = db.query(TrainState).first()
        if not state:
            state = TrainState(speed=60)
            db.add(state)

        if ratio > 0.75:
            state.speed += 1
        elif ratio < 0.25:
            state.speed -= 1

        db.commit()
    finally:
        db.close()


def setup_scheduler() -> AsyncIOScheduler:
    scheduler.add_job(scheduled_resurrect,       "interval", minutes=1)
    scheduler.add_job(scheduled_midnight_recovery, "cron",   hour=0,  minute=0)
    scheduler.add_job(scheduled_train_speed,       "cron",   hour=12, minute=0)
    return scheduler
