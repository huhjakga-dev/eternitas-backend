from pydantic import BaseModel
from typing import Literal

StatType = Literal["health", "mentality", "strength", "inteligence", "luckiness"]


class CreateSession(BaseModel):
    cargo_id:  str
    crew_ids:  list[str] = []


class PrecursorCalculate(BaseModel):
    pattern_id: str
    is_success: bool
    crew_id:    str
    stat:       StatType


class WorkCommand(BaseModel):
    stat:  StatType
    count: int


class MainWorkBody(BaseModel):
    crew_id:  str
    commands: list[WorkCommand]
