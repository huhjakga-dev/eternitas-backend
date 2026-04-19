import uuid
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from src.database import Base


class TrainState(Base):
    __tablename__ = "train_state"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    speed      = Column(Integer, default=60, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
