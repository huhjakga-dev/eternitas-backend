from contextlib import asynccontextmanager
from fastapi import FastAPI
from precursors.router import router as precursor_router
from precursors.service import PrecursorService
from database import connect_db, disconnect_db

app = FastAPI(
    title="eternitas (열차커) 운영 및 러너 참여 컨텐츠 보조 서버",
    description="""
    밴드 커뮤니티 'ETERNITAS: The 60mph Orbit'의 운영에 필요한 기능들을 제공합니다. 해당 커뮤니티에서 이뤄지는 모든 데이터 수집은 커뮤니티 운영에만 사용되며, 커뮤니티 엔딩 후에는 러너(밴드 멤버)들의 의사에 따라 파기 혹은 러너에게 전달(단, 본인이 생성한 데이터에 한해)됩니다!
    """,
)
app.include_router(precursor_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_conn = connect_db()

    start_scheduler()
    with Session(bind=db_conn) as session:
        create_missing_previous_day_reports(db_session=session)
    yield
    disconnect_db()
    stop_scheduler()


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
