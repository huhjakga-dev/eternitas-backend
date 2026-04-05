from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from database import Base


class CargoPrecursor(Base):
    __tablename__ = "cargo_precursors"

    id = Column(Integer, primary_key=True, index=True)
    post_key = Column(String, unique=True, nullable=False, index=True)
    cargo_id = Column(Integer, ForeignKey("cargos.id"), nullable=False)

    # waiting(선언대기) -> active(대응대기) -> resolved(종료)
    status = Column(String, default="waiting")

    pattern_id = Column(Integer, ForeignKey("cargo_patterns.id"), nullable=True)
    declaration_comment_id = Column(String, nullable=True)

    crew_id = Column(Integer, ForeignKey("crews.id"), nullable=True)
    response_comment_id = Column(String, nullable=True)

    result = Column(String, nullable=True)  # success, fail
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
