from pydantic import BaseModel
from typing import Literal
from src.common.schema import PrecursorResult


class CreateSession(BaseModel):
    cargo_id:  str
    crew_ids:  list[str]    = []


class PrecursorDeclarationBody(BaseModel):
    pass  # comment_key 불필요 — session당 1회


class CrewResponseBody(BaseModel):
    crew_id: str
    result:  PrecursorResult


class WorkCommand(BaseModel):
    stat:  Literal["health", "mentality", "strength", "inteligence", "luckiness"]
    count: int


class MainWorkBody(BaseModel):
    crew_id:  str
    commands: list[WorkCommand]
