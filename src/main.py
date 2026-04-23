from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.scheduler import setup_scheduler
from src.works.router import router as works_router
from src.runners.router import router as runners_router
from src.train.router import router as train_router
from src.reisolation.router import router as reisolation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = setup_scheduler()
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
app.include_router(train_router)
app.include_router(reisolation_router)


@app.get("/health")
def health():
    return {"status": "ok"}
