from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trip_incident import TripIncident
from app.models.trip import Trip
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.models.trip_assignment import TripAssignment

from app.services.trip_assignment_service import (
    replace_active_assignment,
)


def get_trip(
    db: Session,
    trip_id: int,
) -> Trip:
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    return trip


def get_incident(
    db: Session,
    incident_id: int,
) -> TripIncident:
    incident = (
        db.query(TripIncident)
        .filter(TripIncident.id == incident_id)
        .first()
    )

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="حادثه پیدا نشد",
        )

    return incident


def get_driver(
    db: Session,
    driver_id: int,
) -> Driver:
    driver = (
        db.query(Driver)
        .filter(Driver.id == driver_id)
        .first()
    )

    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده موردنظر پیدا نشد",
        )

    return driver


def get_vehicle(
    db: Session,
    vehicle_id: int,
) -> Vehicle:
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .first()
    )

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو موردنظر پیدا نشد",
        )

    return vehicle


def validate_trip_for_incident(
    trip: Trip,
) -> None:
    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )


def validate_driver_for_trip(
    driver: Driver,
    trip: Trip,
) -> None:
    if driver.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به دانشگاه این سفر نیست",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده غیرفعال است",
        )


def validate_vehicle_for_trip(
    vehicle: Vehicle,
    trip: Trip,
) -> None:
    if vehicle.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو متعلق به دانشگاه این سفر نیست",
        )

    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو غیرفعال است",
        )


def validate_occurred_at(
    occurred_at: datetime,
) -> None:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان وقوع حادثه باید دارای منطقه زمانی باشد",
        )

    now = datetime.now(timezone.utc)

    if occurred_at.astimezone(timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان وقوع حادثه نمی‌تواند در آینده باشد",
        )


def create_trip_incident(
    db: Session,
    *,
    trip_id: int,
    reported_by_driver_id: int | None,
    incident_type: str,
    description: str | None,
    occurred_at: datetime,
) -> TripIncident:

    trip = get_trip(
        db,
        trip_id,
    )

    validate_trip_for_incident(
        trip,
    )

    if reported_by_driver_id is not None:
        driver = get_driver(
            db,
            reported_by_driver_id,
        )

        validate_driver_for_trip(
            driver,
            trip,
        )

    validate_occurred_at(
        occurred_at,
    )

    incident = TripIncident(
        trip_id=trip.id,
        reported_by_driver_id=reported_by_driver_id,
        incident_type=incident_type,
        description=description,
        occurred_at=occurred_at,
        resolved_at=None,
        is_resolved=False,
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


def get_trip_incidents(
    db: Session,
    *,
    trip_id: int | None = None,
    is_resolved: bool | None = None,
    incident_type: str | None = None,
) -> list[TripIncident]:

    query = (
        db.query(TripIncident)
        .join(
            Trip,
            Trip.id == TripIncident.trip_id,
        )
    )

    if trip_id is not None:
        query = query.filter(
            TripIncident.trip_id == trip_id
        )

    if is_resolved is not None:
        query = query.filter(
            TripIncident.is_resolved == is_resolved
        )

    if incident_type is not None:
        incident_type = incident_type.strip()

        if incident_type:
            query = query.filter(
                TripIncident.incident_type == incident_type
            )

    return (
        query
        .order_by(
            TripIncident.occurred_at.desc()
        )
        .all()
    )


def resolve_trip_incident(
    db: Session,
    *,
    incident_id: int,
) -> TripIncident:

    incident = get_incident(
        db,
        incident_id,
    )

    if incident.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این حادثه قبلاً رسیدگی شده است",
        )

    incident.is_resolved = True
    incident.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)

    return incident


def create_replacement_assignment(
    db: Session,
    *,
    incident_id: int,
    assigned_by_user_id: int,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    reason: str | None = None,
) -> TripAssignment:

    if driver_id is None and vehicle_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل راننده یا خودرو جایگزین باید مشخص شود",
        )

    incident = get_incident(
        db,
        incident_id,
    )

    trip = get_trip(
        db,
        incident.trip_id,
    )

    if trip.status in {"completed", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای سفر پایان‌یافته یا لغوشده امکان جایگزینی وجود ندارد",
        )

    if driver_id is not None:
        driver = get_driver(
            db,
            driver_id,
        )

        validate_driver_for_trip(
            driver,
            trip,
        )

    if vehicle_id is not None:
        vehicle = get_vehicle(
            db,
            vehicle_id,
        )

        validate_vehicle_for_trip(
            vehicle,
            trip,
        )

    current_assignment = (
        db.query(TripAssignment)
        .filter(
            TripAssignment.trip_id == trip.id,
            TripAssignment.is_active.is_(True),
        )
        .order_by(
            TripAssignment.id.desc(),
        )
        .first()
    )

    if current_assignment is not None:
        if driver_id is None:
            driver_id = current_assignment.driver_id

        if vehicle_id is None:
            vehicle_id = current_assignment.vehicle_id

    if driver_id is None and vehicle_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="منابع جایگزین معتبر نیستند",
        )

    assignment = TripAssignment(
        trip_id=trip.id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        assigned_by_user_id=assigned_by_user_id,
        assignment_type="substitute",
        reason=(
            reason.strip()
            if reason and reason.strip()
            else f"جایگزینی به علت حادثه شماره {incident.id}"
        ),
        start_at=datetime.now(timezone.utc),
        end_at=None,
        is_active=False,
    )

    try:
        db.add(assignment)
        db.flush()

        replace_active_assignment(
            db=db,
            trip=trip,
            new_assignment=assignment,
        )

        db.commit()
        db.refresh(assignment)

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    return assignment


def replace_trip_resources(
    db: Session,
    *,
    incident_id: int,
    assigned_by_user_id: int,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    reason: str | None = None,
) -> TripAssignment:
    return create_replacement_assignment(
        db=db,
        incident_id=incident_id,
        assigned_by_user_id=assigned_by_user_id,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        reason=reason,
    )