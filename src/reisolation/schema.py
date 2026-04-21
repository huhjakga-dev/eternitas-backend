from pydantic import BaseModel


class CreateReIsolationSession(BaseModel):
    cargo_id:  str
    crew_ids:  list[str] = []


class ReIsolationAttack(BaseModel):
    crew_id: str
