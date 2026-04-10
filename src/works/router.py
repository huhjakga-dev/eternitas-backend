from fastapi import APIRouter, Depends
from src.database import DbSession
from .service import WorkService
from .worker import work_polling_worker

router = APIRouter(prefix="/works", tags=["Works"])


@router.post("/collect")
async def collect_today_works(db: DbSession):
    """수동으로 오늘 작업 세션 수집 트리거"""
    service = WorkService(db)
    new_sessions = await service.collect_today_works()
    return {"message": f"{len(new_sessions)}개의 새 세션이 등록되었습니다."}


@router.post("/polling")
async def trigger_polling():
    """수동으로 폴링 워커 한 바퀴 실행"""
    await work_polling_worker()
    return {"message": "폴링 완료"}
