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


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(scheduled_resurrect, "interval", minutes=1)
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
