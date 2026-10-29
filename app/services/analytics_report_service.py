from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.route import Route
from app.models.service import Service
from app.models.trip import Trip


COMPLETED_TRIP_STATUS = "completed"


def get_trip_summary(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
    service_id: int | None = None,
    route_id: int | None = None,
):
    query = (
        db.query(
            func.count(Trip.id).label("trip_count"),
            func.count(
                func.distinct(Trip.service_id)
            ).label("service_count"),
            func.count(
                func.distinct(Service.route_id)
            ).label("route_count"),
            func.coalesce(
                func.sum(Trip.seated_capacity),
                0,
            ).label("total_capacity"),
        )
        .join(
            Service,
            Service.id == Trip.service_id,
        )
        .filter(
            Trip.is_active.is_(True),
        )
    )

    if start_date is not None:
        query = query.filter(
            Trip.trip_date >= start_date,
        )

    if end_date is not None:
        query = query.filter(
            Trip.trip_date <= end_date,
        )

    if university_id is not None:
        query = query.filter(
            Trip.university_id == university_id,
        )

    if service_id is not None:
        query = query.filter(
            Trip.service_id == service_id,
        )

    if route_id is not None:
        query = query.filter(
            Service.route_id == route_id,
        )

    row = query.one()

    return {
        "trip_count": int(row.trip_count or 0),
        "service_count": int(row.service_count or 0),
        "route_count": int(row.route_count or 0),
        "total_capacity": int(row.total_capacity or 0),
    }


def get_completed_trip_summary(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
    service_id: int | None = None,
    route_id: int | None = None,
):
    query = (
        db.query(
            func.count(Trip.id).label("completed_trip_count"),
            func.coalesce(
                func.sum(Trip.seated_capacity),
                0,
            ).label("total_capacity"),
        )
        .join(
            Service,
            Service.id == Trip.service_id,
        )
        .filter(
            Trip.is_active.is_(True),
            Trip.status == COMPLETED_TRIP_STATUS,
        )
    )

    if start_date is not None:
        query = query.filter(
            Trip.trip_date >= start_date,
        )

    if end_date is not None:
        query = query.filter(
            Trip.trip_date <= end_date,
        )

    if university_id is not None:
        query = query.filter(
            Trip.university_id == university_id,
        )

    if service_id is not None:
        query = query.filter(
            Trip.service_id == service_id,
        )

    if route_id is not None:
        query = query.filter(
            Service.route_id == route_id,
        )

    row = query.one()

    return {
        "completed_trip_count": int(
            row.completed_trip_count or 0
        ),
        "total_capacity": int(
            row.total_capacity or 0
        ),
    }


def get_reservation_summary(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
    service_id: int | None = None,
    route_id: int | None = None,
):
    query = (
        db.query(
            func.count(Reservation.id).label(
                "reservation_count"
            ),
            func.count(
                func.distinct(Reservation.student_id)
            ).label("student_count"),
        )
        .join(
            Trip,
            Trip.id == Reservation.trip_id,
        )
        .join(
            Service,
            Service.id == Trip.service_id,
        )
        .filter(
            Reservation.status == "active",
            Trip.is_active.is_(True),
        )
    )

    if start_date is not None:
        query = query.filter(
            Trip.trip_date >= start_date,
        )

    if end_date is not None:
        query = query.filter(
            Trip.trip_date <= end_date,
        )

    if university_id is not None:
        query = query.filter(
            Trip.university_id == university_id,
        )

    if service_id is not None:
        query = query.filter(
            Trip.service_id == service_id,
        )

    if route_id is not None:
        query = query.filter(
            Service.route_id == route_id,
        )

    row = query.one()

    return {
        "active_reservation_count": int(
            row.reservation_count or 0
        ),
        "reserved_student_count": int(
            row.student_count or 0
        ),
    }


def get_route_usage_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
):
    query = (
        db.query(
            Route.id.label("route_id"),
            Route.name.label("route_name"),
            Service.id.label("service_id"),
            Service.name.label("service_name"),
            func.count(
                func.distinct(Trip.id)
            ).label("completed_trip_count"),
            func.coalesce(
                func.sum(Trip.seated_capacity),
                0,
            ).label("total_capacity"),
            func.count(Reservation.id).label(
                "reservation_count"
            ),
        )
        .join(
            Service,
            Service.route_id == Route.id,
        )
        .join(
            Trip,
            (
                (Trip.service_id == Service.id)
                & (Trip.status == COMPLETED_TRIP_STATUS)
                & (Trip.is_active.is_(True))
            ),
        )
        .outerjoin(
            Reservation,
            (
                (Reservation.trip_id == Trip.id)
                & (Reservation.status == "active")
            ),
        )
        .filter(
            Route.is_active.is_(True),
            Service.is_active.is_(True),
        )
    )

    if start_date is not None:
        query = query.filter(
            Trip.trip_date >= start_date,
        )

    if end_date is not None:
        query = query.filter(
            Trip.trip_date <= end_date,
        )

    if university_id is not None:
        query = query.filter(
            Service.university_id == university_id,
        )

    query = (
        query.group_by(
            Route.id,
            Route.name,
            Service.id,
            Service.name,
        )
        .order_by(
            Route.id,
            Service.id,
        )
    )

    rows = query.all()

    result = []

    for row in rows:
        total_capacity = int(
            row.total_capacity or 0
        )
        reservation_count = int(
            row.reservation_count or 0
        )
        completed_trip_count = int(
            row.completed_trip_count or 0
        )

        usage_percent = 0.0

        if total_capacity > 0:
            usage_percent = round(
                reservation_count
                / total_capacity
                * 100,
                2,
            )

        result.append(
            {
                "route_id": row.route_id,
                "route_name": row.route_name,
                "service_id": row.service_id,
                "service_name": row.service_name,
                "completed_trip_count": completed_trip_count,
                "total_capacity": total_capacity,
                "reservation_count": reservation_count,
                "usage_percent": usage_percent,
            }
        )

    return result


def get_analytics_report(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    university_id: int | None = None,
    service_id: int | None = None,
    route_id: int | None = None,
):
    trip_summary = get_trip_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
        service_id=service_id,
        route_id=route_id,
    )

    completed_trip_summary = get_completed_trip_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
        service_id=service_id,
        route_id=route_id,
    )

    reservation_summary = get_reservation_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
        service_id=service_id,
        route_id=route_id,
    )

    route_usage = get_route_usage_report(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
    )

    total_capacity = completed_trip_summary[
        "total_capacity"
    ]

    total_reservations = reservation_summary[
        "active_reservation_count"
    ]

    overall_usage_percent = 0.0

    if total_capacity > 0:
        overall_usage_percent = round(
            total_reservations
            / total_capacity
            * 100,
            2,
        )

    return {
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "university_id": university_id,
            "service_id": service_id,
            "route_id": route_id,
        },
        "summary": {
            "trip_count": trip_summary["trip_count"],
            "completed_trip_count": completed_trip_summary[
                "completed_trip_count"
            ],
            "service_count": trip_summary["service_count"],
            "route_count": trip_summary["route_count"],
            "total_capacity": total_capacity,
            "active_reservation_count": total_reservations,
            "reserved_student_count": reservation_summary[
                "reserved_student_count"
            ],
            "overall_usage_percent": overall_usage_percent,
        },
        "route_usage": route_usage,
    }