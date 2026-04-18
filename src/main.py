from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from datetime import datetime, timezone, timedelta
from src.database import SessionLocal
from src.works.router import router as works_router
from src.runners.router import router as runners_router
from src.runners.models import Crew


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
            crew.is_dead = False
            crew.death_time = None
            crew.mechanization_lv = min((crew.mechanization_lv or 0) + 1, 4)
            mech_hp_mult = {0: 1.0, 1: 1.0, 2: 1.1, 3: 1.3, 4: 1.5}
            mech_sp_mult = {0: 1.0, 1: 1.0, 2: 0.8, 3: 0.6, 4: 0.5}
            new_lv = crew.mechanization_lv
            crew.hp = round((crew.health or 1) * 5 * mech_hp_mult[new_lv])
            crew.sp = round((crew.mentality or 1) * 5 * mech_sp_mult[new_lv])
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
            max_hp = crew.max_hp or (crew.health or 1) * 5
            max_sp = crew.max_sp or (crew.mentality or 1) * 5
            hp = crew.hp or 0
            sp = crew.sp or 0

            if hp > max_hp // 2:
                hp_gain = 10
            else:
                hp_gain = 10 + int((max_hp / 2 - hp) * 0.6)

            if sp > max_sp // 2:
                sp_gain = 10
            else:
                sp_gain = 10 + int((max_sp / 2 - sp) * 0.6)

            crew.hp = min(max_hp, hp + hp_gain)
            crew.sp = min(max_sp, sp + sp_gain)

        if crews:
            db.commit()
    finally:
        db.close()


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(scheduled_resurrect, "interval", minutes=1)
    scheduler.add_job(scheduled_midnight_recovery, "cron", hour=0, minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="eternitas",
    description="ETERNITAS: The 60mph Orbit 운영 보조 서버",
    lifespan=lifespan,
)

app.include_router(runners_router)
app.include_router(works_router)


@app.get("/health")
def health():
    return {"status": "ok"}
