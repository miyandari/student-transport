from fastapi import APIRouter

from app.api import station_events
from app.api import contract_drivers
from app.api import contract_vehicles
from app.api import transport_companies
from app.api import trip_assignments
from app.api import audit_logs

router = APIRouter()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "Backend سامانه فعال است",
    }


# =========================================================
# Routers
# =========================================================

router.include_router(
    station_events.router
)

router.include_router(
    contract_drivers.router
)

router.include_router(
    contract_vehicles.router
)

router.include_router(
    transport_companies.router
)

router.include_router(
    trip_assignments.router
)

router.include_router(
    audit_logs.router
)