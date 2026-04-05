from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from .service import PrecursorService

router = APIRouter(prefix="/precursors", tags=["Precursors"])


@router.post("/batch-register")
async def batch_register(db: Session = Depends(get_db)):
    """관리 시간 10분 뒤, 게시글 싹 긁어서 등록하는 버튼/API"""
    service = PrecursorService(db)
    # 1. 밴드에서 최근 글 리스트 GET
    # 2. service.register_batch_posts(posts) 호출
    return {"message": "일괄 등록 완료"}


@router.get("/polling-trigger")
async def trigger_polling(db: Session = Depends(get_db)):
    """강제로 폴링 한 바퀴 돌리기 (또는 스케줄러가 호출)"""
    service = PrecursorService(db)
    await service.poll_and_update()
    return {"status": "polling completed"}
