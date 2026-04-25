"""
화물 이름 → 서비스 클래스 레지스트리.
새 화물 서비스를 추가할 때 여기에 등록한다.
"""
from .base import BaseCargoService, GenericCargoService
from .b156 import SpreadingThirstService
from .a125 import A125Service

REGISTRY: dict[str, type[BaseCargoService]] = {
    "B-156": SpreadingThirstService,
    "A-125":           A125Service,
}


def get_cargo_service(
    cargo_name: str,
) -> type[BaseCargoService]:
    """등록된 서비스가 없으면 GenericCargoService를 반환한다."""
    return REGISTRY.get(cargo_name, GenericCargoService)
