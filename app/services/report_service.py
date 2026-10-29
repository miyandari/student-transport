from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.driver import Driver
from app.models.reservation import Reservation
from app.models.service import Service
from app.models.trip import Trip
from app.models.trip_incident import TripIncident
from app.models.trip_passenger import TripPassenger
from app.models.vehicle import Vehicle


def validate_report_period(
    from_date: date,
    to_date: date,
) -> None:
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="تاریخ شروع گزارش نمی‌تواند بعد از تاریخ پایان باشد",
        )


def validate_university_id(university_id: int) -> None:
    if university_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="شناسه دانشگاه باید بزرگ‌تر از صفر باشد",
        )


def get_trip_query(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    validate_university_id(university_id)
    validate_report_period(from_date, to_date)

    return db.query(Trip).filter(
        Trip.university_id == university_id,
        Trip.trip_date >= from_date,
        Trip.trip_date <= to_date,
    )


def get_transport_summary(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    validate_report_period(from_date, to_date)

    trips = get_trip_query(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    ).all()

    trip_ids = [trip.id for trip in trips]

    total_trips = len(trips)
    completed_trips = sum(
        1 for trip in trips if trip.status == "completed"
    )
    cancelled_trips = sum(
        1 for trip in trips if trip.status == "cancelled"
    )
    scheduled_trips = sum(
        1 for trip in trips if trip.status == "scheduled"
    )

    total_reservations = 0
    active_reservations = 0
    waitlisted_reservations = 0
    cancelled_reservations = 0

    total_boarded_passengers = 0
    seated_passengers = 0
    standing_passengers = 0
    boarding_without_reservation = 0

    if trip_ids:
        reservations = db.query(Reservation).filter(
            Reservation.trip_id.in_(trip_ids)
        ).all()

        total_reservations = len(reservations)
        active_reservations = sum(
            1 for item in reservations
            if item.status == "active"
        )
        waitlisted_reservations = sum(
            1 for item in reservations
            if item.status == "waitlisted"
        )
        cancelled_reservations = sum(
            1 for item in reservations
            if item.status == "cancelled"
        )

        passengers = db.query(TripPassenger).filter(
            TripPassenger.trip_id.in_(trip_ids),
            TripPassenger.boarding_time.is_not(None),
        ).all()

        total_boarded_passengers = len(passengers)
        seated_passengers = sum(
            1 for item in passengers
            if not item.is_standing
        )
        standing_passengers = sum(
            1 for item in passengers
            if item.is_standing
        )
        boarding_without_reservation = sum(
            1 for item in passengers
            if item.boarding_method == "qr_without_reservation"
        )

    no_show_students = 0

    if trip_ids:
        completed_trip_ids = [
            trip.id
            for trip in trips
            if trip.status == "completed"
        ]

        if completed_trip_ids:
            no_show_students = (
                db.query(
                    func.count(func.distinct(Reservation.student_id))
                )
                .outerjoin(
                    TripPassenger,
                    (
                        (TripPassenger.trip_id == Reservation.trip_id)
                        & (
                            TripPassenger.student_id
                            == Reservation.student_id
                        )
                    ),
                )
                .filter(
                    Reservation.trip_id.in_(completed_trip_ids),
                    Reservation.status == "active",
                    TripPassenger.id.is_(None),
                )
                .scalar()
                or 0
            )

    return {
        "university_id": university_id,
        "from_date": from_date,
        "to_date": to_date,
        "total_trips": total_trips,
        "completed_trips": completed_trips,
        "cancelled_trips": cancelled_trips,
        "scheduled_trips": scheduled_trips,
        "total_reservations": total_reservations,
        "active_reservations": active_reservations,
        "waitlisted_reservations": waitlisted_reservations,
        "cancelled_reservations": cancelled_reservations,
        "total_boarded_passengers": total_boarded_passengers,
        "seated_passengers": seated_passengers,
        "standing_passengers": standing_passengers,
        "boarding_without_reservation": boarding_without_reservation,
        "no_show_students": no_show_students,
    }


def get_financial_report(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    validate_university_id(university_id)
    validate_report_period(from_date, to_date)

    contracts = db.query(Contract).filter(
        Contract.university_id == university_id,
        Contract.is_active.is_(True),
        Contract.start_date <= to_date,
        Contract.end_date >= from_date,
    ).all()

    total_contract_amount = sum(
        int(contract.contract_amount or 0)
        for contract in contracts
    )

    trips = get_trip_query(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    ).all()

    completed_trips = [
        trip for trip in trips
        if trip.status == "completed"
    ]

    trip_ids = [trip.id for trip in trips]

    total_boarded_passengers = 0

    if trip_ids:
        total_boarded_passengers = (
            db.query(func.count(TripPassenger.id))
            .filter(
                TripPassenger.trip_id.in_(trip_ids),
                TripPassenger.boarding_time.is_not(None),
            )
            .scalar()
            or 0
        )

    cost_per_completed_trip = None
    cost_per_boarded_passenger = None

    if completed_trips and total_contract_amount:
        cost_per_completed_trip = round(
            total_contract_amount / len(completed_trips),
            2,
        )

    if total_boarded_passengers and total_contract_amount:
        cost_per_boarded_passenger = round(
            total_contract_amount / total_boarded_passengers,
            2,
        )

    return {
        "university_id": university_id,
        "from_date": from_date,
        "to_date": to_date,
        "active_contracts": len(contracts),
        "total_contract_amount": total_contract_amount,
        "total_trips": len(trips),
        "completed_trips": len(completed_trips),
        "total_boarded_passengers": total_boarded_passengers,
        "cost_per_completed_trip": cost_per_completed_trip,
        "cost_per_boarded_passenger": cost_per_boarded_passenger,
    }


def get_route_usage_report(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    trips = get_trip_query(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    ).all()

    services = db.query(Service).filter(
        Service.university_id == university_id
    ).all()

    result = []

    for service in services:
        service_trips = [
            trip for trip in trips
            if trip.service_id == service.id
        ]

        if not service_trips:
            continue

        trip_ids = [trip.id for trip in service_trips]

        boarded = 0

        if trip_ids:
            boarded = (
                db.query(func.count(TripPassenger.id))
                .filter(
                    TripPassenger.trip_id.in_(trip_ids),
                    TripPassenger.boarding_time.is_not(None),
                )
                .scalar()
                or 0
            )

        completed_trips = sum(
            1
            for trip in service_trips
            if trip.status == "completed"
        )

        average_passengers = round(
            boarded / len(service_trips),
            2,
        )

        total_capacity = sum(
            int(trip.seated_capacity or 0)
            for trip in service_trips
        )

        utilization_percent = 0.0

        if total_capacity > 0:
            utilization_percent = round(
                (boarded / total_capacity) * 100,
                2,
            )

        result.append(
            {
                "service_id": service.id,
                "service_name": service.name,
                "total_trips": len(service_trips),
                "completed_trips": completed_trips,
                "boarded_passengers": boarded,
                "average_passengers_per_trip": average_passengers,
                "utilization_percent": utilization_percent,
            }
        )

    return result


def get_driver_performance_report(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    trips = get_trip_query(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    ).all()

    drivers = db.query(Driver).filter(
        Driver.university_id == university_id
    ).all()

    result = []

    for driver in drivers:
        driver_trips = [
            trip for trip in trips
            if trip.driver_id == driver.id
        ]

        if not driver_trips:
            continue

        trip_ids = [trip.id for trip in driver_trips]

        boarded_passengers = 0

        if trip_ids:
            boarded_passengers = (
                db.query(func.count(TripPassenger.id))
                .filter(
                    TripPassenger.trip_id.in_(trip_ids),
                    TripPassenger.boarding_time.is_not(None),
                )
                .scalar()
                or 0
            )

        incidents_count = (
            db.query(func.count(TripIncident.id))
            .join(
                Trip,
                Trip.id == TripIncident.trip_id,
            )
            .filter(
                Trip.university_id == university_id,
                Trip.driver_id == driver.id,
                Trip.trip_date >= from_date,
                Trip.trip_date <= to_date,
            )
            .scalar()
            or 0
        )

        result.append(
            {
                "driver_id": driver.id,
                "driver_name": (
                    f"{driver.first_name} {driver.last_name}"
                ),
                "total_trips": len(driver_trips),
                "completed_trips": sum(
                    1
                    for trip in driver_trips
                    if trip.status == "completed"
                ),
                "cancelled_trips": sum(
                    1
                    for trip in driver_trips
                    if trip.status == "cancelled"
                ),
                "total_boarded_passengers": boarded_passengers,
                "no_show_related_incidents": incidents_count,
            }
        )

    return result


def get_vehicle_usage_report(
    db: Session,
    *,
    university_id: int,
    from_date: date,
    to_date: date,
):
    trips = get_trip_query(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    ).all()

    vehicles = db.query(Vehicle).filter(
        Vehicle.university_id == university_id
    ).all()

    result = []

    for vehicle in vehicles:
        vehicle_trips = [
            trip for trip in trips
            if trip.vehicle_id == vehicle.id
        ]

        if not vehicle_trips:
            continue

        trip_ids = [trip.id for trip in vehicle_trips]

        boarded = 0

        if trip_ids:
            boarded = (
                db.query(func.count(TripPassenger.id))
                .filter(
                    TripPassenger.trip_id.in_(trip_ids),
                    TripPassenger.boarding_time.is_not(None),
                )
                .scalar()
                or 0
            )

        identifier = getattr(
            vehicle,
            "plate_number",
            None,
        ) or getattr(
            vehicle,
            "code",
            None,
        ) or str(vehicle.id)

        result.append(
            {
                "vehicle_id": vehicle.id,
                "vehicle_identifier": identifier,
                "total_trips": len(vehicle_trips),
                "completed_trips": sum(
                    1
                    for trip in vehicle_trips
                    if trip.status == "completed"
                ),
                "boarded_passengers": boarded,
                "average_passengers_per_trip": round(
                    boarded / len(vehicle_trips),
                    2,
                ),
            }
        )

    return result


def get_report_generated_at() -> datetime:
    return datetime.now(timezone.utc)