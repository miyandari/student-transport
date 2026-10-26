from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import (
    check_university_access,
    check_trip_company_access,
    get_current_user,
)
from app.core.roles import Roles
from app.database import get_db

from app.models.trip import Trip
from app.models.user import User

from app.schemas.station_event import (
    StationEventResponse,
    StationStopDurationResponse,
    TripDelayReportItem,
    TripStationReportItem,
)

from app.services.station_event_service import (
    get_station_events,
    get_station_stop_duration,
    get_trip_delay_report,
    get_trip_station_report,
)


router = APIRouter(
    prefix="/station-events",
    tags=["Station Events"],
)


def get_accessible_trip(
    db: Session,
    *,
    trip_id: int,
    current_user: User,
) -> Trip:

    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id,
            Trip.is_active.is_(True),
        )
        .first()
    )

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    # -------------------------------------------------
    # کنترل دسترسی شرکت حمل‌ونقل
    # -------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db,
            current_user,
            trip,
        )

    # -------------------------------------------------
    # کنترل دسترسی سایر کاربران
    # -------------------------------------------------

    else:

        check_university_access(
            current_user=current_user,
            university_id=trip.university_id,
        )

    return trip


@router.get(
    "/trips/{trip_id}",
    response_model=list[StationEventResponse],
)
def get_trip_station_events(
    trip_id: int,
    station_id: int | None = Query(
        default=None,
        gt=0,
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_accessible_trip(
        db,
        trip_id=trip_id,
        current_user=current_user,
    )

    return get_station_events(
        db,
        trip_id=trip_id,
        station_id=station_id,
    )


@router.get(
    "/trips/{trip_id}/stations/{station_id}/stop-duration",
    response_model=StationStopDurationResponse,
)
def get_trip_station_stop_duration(
    trip_id: int,
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_accessible_trip(
        db,
        trip_id=trip_id,
        current_user=current_user,
    )

    result = get_station_stop_duration(
        db,
        trip_id=trip_id,
        station_id=station_id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="اطلاعات کامل توقف این ایستگاه هنوز ثبت نشده است",
        )

    return result


@router.get(
    "/trips/{trip_id}/report",
    response_model=list[TripStationReportItem],
)
def get_trip_station_report_api(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_accessible_trip(
        db,
        trip_id=trip_id,
        current_user=current_user,
    )

    return get_trip_station_report(
        db,
        trip_id=trip_id,
    )


@router.get(
    "/trips/{trip_id}/delay-report",
    response_model=list[TripDelayReportItem],
)
def get_trip_delay_report_api(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_accessible_trip(
        db,
        trip_id=trip_id,
        current_user=current_user,
    )

    return get_trip_delay_report(
        db,
        trip_id=trip_id,
    )