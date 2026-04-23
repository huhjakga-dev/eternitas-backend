from fastapi import APIRouter
from .crew import router as crew_router
from .cargo import router as cargo_router
from .equipment import router as equipment_router
from .status_effect import router as status_effect_router

router = APIRouter(prefix="/runners", tags=["Runners"])
router.include_router(crew_router)
router.include_router(cargo_router)
router.include_router(equipment_router)
router.include_router(status_effect_router)
