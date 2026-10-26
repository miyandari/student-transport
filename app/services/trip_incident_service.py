from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trip_incident import TripIncident
from app.models.trip import Trip
from app.models.driver import Driver


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
            detail="راننده گزارش‌دهنده پیدا نشد",
        )

    return driver


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
            detail="راننده گزارش‌دهنده غیرفعال است",
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