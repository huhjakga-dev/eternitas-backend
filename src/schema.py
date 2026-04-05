from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from precursors.router import router as precursor_router
from precursors.service import PrecursorService
from database import SessionLocal

app = FastAPI()
app.include_router(precursor_router)

scheduler = BackgroundScheduler()


def scheduled_polling():
    # 여기서 DB 세션을 직접 열어서 폴링 실행
    db = SessionLocal()
    try:
        service = PrecursorService(db)
        # async 함수이므로 적절한 비동기 루프 처리 필요
        import asyncio

        asyncio.run(service.poll_and_update())
    finally:
        db.close()


# 5분 간격으로 폴링 실행 (운영 시간 체크 로직 추가 가능)
scheduler.add_job(scheduled_polling, "interval", minutes=5)
scheduler.start()
