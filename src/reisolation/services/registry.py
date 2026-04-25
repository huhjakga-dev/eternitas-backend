"""
화물 이름 → 재격리 서비스 클래스 레지스트리.
새 화물 서비스를 추가할 때 여기에 등록한다.
"""
from .base import BaseReisolationService, GenericReisolationService
from .a125 import A125ReisolationService

REGISTRY: dict[str, type[BaseReisolationService]] = {
    "A-125": A125ReisolationService,
}


def get_reisolation_service(cargo_name: str) -> type[BaseReisolationService]:
    """등록된 서비스가 없으면 GenericReisolationService를 반환한다."""
    return REGISTRY.get(cargo_name, GenericReisolationService)
