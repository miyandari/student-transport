from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.schemas.trip_incident import (
    TripIncidentCreate,
    TripIncidentResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_trip_company_access,
)

from app.core.roles import (
    Roles,
)

from app.services.trip_incident_service import (
    get_trip,
    get_incident,
    create_trip_incident,
    get_trip_incidents,
    resolve_trip_incident,
)


router = APIRouter(
    prefix="/trip-incidents",
    tags=["Trip Incidents"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}

WRITE_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
    Roles.DRIVER,
}

VIEW_ROLES = WRITE_ROLES


def check_trip_access(
    db: Session,
    current_user: User,
    trip,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db,
            current_user,
            trip,
        )

    else:

        check_university_access(
            current_user=current_user,
            university_id=trip.university_id,
        )


def check_driver_trip_access(
    current_user: User,
    trip,
) -> None:

    if current_user.role != Roles.DRIVER:
        return

    if current_user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری راننده به یک راننده متصل نیست",
        )

    if trip.driver_id != current_user.driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است",
        )


@router.post(
    "/",
    response_model=TripIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_incident_endpoint(
    incident_data: TripIncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ثبت حادثه ندارید",
        )

    trip = get_trip(
        db,
        incident_data.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    # راننده فقط می‌تواند حادثه را به نام خودش ثبت کند.
    if current_user.role == Roles.DRIVER:

        if current_user.driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری راننده به یک راننده متصل نیست",
            )

        reported_by_driver_id = current_user.driver_id

    else:

        reported_by_driver_id = incident_data.reported_by_driver_id

    incident = create_trip_incident(
        db,
        trip_id=incident_data.trip_id,
        reported_by_driver_id=reported_by_driver_id,
        incident_type=incident_data.incident_type,
        description=incident_data.description,
        occurred_at=incident_data.occurred_at,
    )

    return incident


@router.get(
    "/",
    response_model=list[TripIncidentResponse],
)
def get_trip_incidents_endpoint(
    trip_id: int | None = None,
    is_resolved: bool | None = None,
    incident_type: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده حوادث را ندارید",
        )

    # -------------------------------------------------
    # حالت جست‌وجوی یک سفر مشخص
    # -------------------------------------------------

    if trip_id is not None:

        trip = get_trip(
            db,
            trip_id,
        )

        check_trip_access(
            db,
            current_user,
            trip,
        )

        check_driver_trip_access(
            current_user,
            trip,
        )

        return get_trip_incidents(
            db,
            trip_id=trip_id,
            is_resolved=is_resolved,
            incident_type=incident_type,
        )

    # -------------------------------------------------
    # دریافت فهرست حوادث
    # -------------------------------------------------

    incidents = get_trip_incidents(
        db,
        trip_id=None,
        is_resolved=is_resolved,
        incident_type=incident_type,
    )

    # -------------------------------------------------
    # مدیر کل
    # -------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:
        return incidents

    # -------------------------------------------------
    # شرکت حمل‌ونقل
    # -------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        filtered_incidents = []

        for incident in incidents:

            trip = incident.trip

            if trip is None:
                continue

            try:

                check_trip_company_access(
                    db,
                    current_user,
                    trip,
                )

                filtered_incidents.append(incident)

            except HTTPException:
                continue

        return filtered_incidents

    # -------------------------------------------------
    # کاربران دانشگاه
    # -------------------------------------------------

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست",
        )

    filtered_incidents = []

    for incident in incidents:

        trip = incident.trip

        if trip is None:
            continue

        if trip.university_id != current_user.university_id:
            continue

        # راننده فقط حوادث سفرهای خودش را می‌بیند.
        if current_user.role == Roles.DRIVER:

            if current_user.driver_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="حساب کاربری راننده به یک راننده متصل نیست",
                )

            if trip.driver_id != current_user.driver_id:
                continue

        filtered_incidents.append(incident)

    return filtered_incidents


@router.get(
    "/{incident_id}",
    response_model=TripIncidentResponse,
)
def get_trip_incident_endpoint(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده حادثه را ندارید",
        )

    incident = get_incident(
        db,
        incident_id,
    )

    trip = get_trip(
        db,
        incident.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    return incident


@router.patch(
    "/{incident_id}/resolve",
    response_model=TripIncidentResponse,
)
def resolve_trip_incident_endpoint(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    RESOLVE_ROLES = {
        Roles.SUPER_ADMIN,
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
        Roles.COMPANY_ADMIN,
    }

    if current_user.role not in RESOLVE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز رسیدگی به حادثه را ندارید",
        )

    incident = get_incident(
        db,
        incident_id,
    )

    trip = get_trip(
        db,
        incident.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    resolved_incident = resolve_trip_incident(
        db,
        incident_id=incident_id,
    )

    return resolved_incident