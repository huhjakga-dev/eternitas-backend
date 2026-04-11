"""
eternitas 메인 애플리케이션.

스케줄러 작업:
  - collect_today_works : 매일 9:11, 10:11 → 오늘 [작업] 게시글을 WorkSession으로 등록
  - work_polling_worker : 3분 간격 → 활성 세션 댓글 감시 및 상태 처리
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.database import SessionLocal
from src.works.service import WorkService
from src.works.worker import work_polling_worker
from src.works.router import router as works_router
from src.runners.router import router as runners_router


# ------------------------------------------------------------------ #
# 스케줄러 래퍼 (DB 세션 생성 → 서비스 호출 → 세션 닫기)
# ------------------------------------------------------------------ #


async def scheduled_collect():
    db = SessionLocal()
    try:
        service = WorkService(db)
        await service.collect_today_works()
    finally:
        db.close()


# ------------------------------------------------------------------ #
# 앱 생명주기: 시작 시 스케줄러 ON, 종료 시 OFF
# ------------------------------------------------------------------ #

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 오늘 작업 수집: 매일 9:11, 10:11
    scheduler.add_job(scheduled_collect, "cron", hour="9,10", minute=11)
    # 폴링 워커: 3분 간격
    scheduler.add_job(work_polling_worker, "interval", minutes=3)
    scheduler.start()

    yield

    scheduler.shutdown()


# ------------------------------------------------------------------ #
# FastAPI 앱
# ------------------------------------------------------------------ #

app = FastAPI(
    title="eternitas",
    description="""
    밴드 커뮤니티 'ETERNITAS: The 60mph Orbit' 운영 보조 서버
    운영에 사용되는 모든 러너(밴드 멤버)들의 정보는 
    [커뮤니티 내에서의 이벤트 진행]에만 사용되며, 5월 9일 커뮤니티 엔딩 날짜 이후 모두 파기됩니다!
    해당 페이지는 api docs 문서로, ui 아직 안 만들어서 게시했습니다. 테스트 엔드포인트들을 사용해보셔도 문제는 없지만 제가 데이터 지우기 귀찮아집니다.
    """,
    lifespan=lifespan,
)

app.include_router(runners_router)
app.include_router(works_router)


@app.get("/health")
def health():
    return {"status": "ok"}
