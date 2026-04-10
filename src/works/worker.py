"""
work_polling_worker: 3분 주기로 실행되는 폴링 워커.
활성 세션(status != resolved)의 밴드 댓글을 감시하며 상태별 핸들러 호출.
"""

from src.database import SessionLocal
from src.common.schema import WorkStatus
from .models import WorkSession
from .service import WorkService


async def work_polling_worker():
    db = SessionLocal()
    service = WorkService(db)

    try:
        # status != resolved 인 세션 전체 조회
        active_sessions = (
            db.query(WorkSession)
            .filter(WorkSession.status != WorkStatus.RESOLVED)
            .all()
        )

        for session in active_sessions:
            comments = await service.band.get_comments(session.post_key)

            for comment in comments:
                content = comment.get("content", "")

                if session.status == WorkStatus.WAITING_PRECURSOR:
                    if "[선언]" in content:
                        await service.handle_precursor_declaration(session, comment)
                        break  # 선언은 세션당 하나

                elif session.status == WorkStatus.PRECURSOR_ACTIVE:
                    if "[대응]" in content:
                        await service.handle_crew_response(session, comment)
                        break  # 대응도 세션당 하나

                elif session.status == WorkStatus.MAIN_WORK_READY:
                    if "[작업]" in content:
                        await service.handle_main_work_execution(session, comment)
                        break

    finally:
        db.close()
