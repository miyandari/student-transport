from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.boarding_request import BoardingRequest
from app.models.reservation import Reservation
from app.models.route_station import RouteStation
from app.models.station import Station
from app.models.trip import Trip
from app.models.trip_passenger import TripPassenger
from app.models.student import Student
from app.services.notification_service import (
    create_low_use_route_notifications,
    create_notification_for_student,
)
from app.services.station_event_service import calculate_distance_meters
from app.services.student_penalty_service import register_no_show

FINAL_STATION_PROXIMITY_METERS = 100
FINAL_STATION_STOP_SPEED_KMH = 5

LOW_USAGE_MIN_COMPLETED_TRIPS = 5
LOW_USAGE_THRESHOLD_PERCENT = 30


def get_trip_final_station(
    db: Session,
    *,
    trip_id: int,
):
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        return None

    if trip.service is None:
        return None

    route_id = trip.service.route_id

    final_route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == route_id,
        )
        .order_by(
            RouteStation.stop_order.desc(),
        )
        .first()
    )

    if final_route_station is None:
        return None

    station = (
        db.query(Station)
        .filter(
            Station.id == final_route_station.station_id,
        )
        .first()
    )

    if station is None:
        return None

    return final_route_station, station


def is_at_final_station(
    db: Session,
    *,
    trip_id: int,
    latitude: float,
    longitude: float,
    speed_kmh: float,
) -> bool:
    result = get_trip_final_station(
        db,
        trip_id=trip_id,
    )

    if result is None:
        return False

    _, station = result

    distance = calculate_distance_meters(
        latitude,
        longitude,
        station.latitude,
        station.longitude,
    )

    return (
        distance <= FINAL_STATION_PROXIMITY_METERS
        and speed_kmh < FINAL_STATION_STOP_SPEED_KMH
    )


def process_trip_no_shows(
    db: Session,
    *,
    trip: Trip,
) -> list[Student]:
    """
    برای رزروهای فعال که دانشجو در سفر سوار نشده است،
    جریمه No-Show ثبت می‌کند.

    رزرو لغوشده و رزروهای صف انتظار مشمول No-Show نیستند.
    برای جلوگیری از جریمه تکراری، AuditLog بررسی می‌شود.
    """

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status == "active",
        )
        .all()
    )

    penalized_students: list[Student] = []

    for reservation in reservations:
        passenger = (
            db.query(TripPassenger)
            .filter(
                TripPassenger.trip_id == trip.id,
                TripPassenger.student_id == reservation.student_id,
                TripPassenger.boarding_time.is_not(None),
            )
            .first()
        )

        if passenger is not None:
            continue

        already_penalized = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "no_show_penalty",
                AuditLog.entity_type == "reservation",
                AuditLog.entity_id == reservation.id,
            )
            .first()
        )

        if already_penalized is not None:
            continue

        student = (
            db.query(Student)
            .filter(
                Student.id == reservation.student_id,
            )
            .first()
        )

        if student is None:
            continue

        old_no_show_count = student.no_show_count
        old_negative_score = student.negative_score

        register_no_show(
            db,
            student=student,
        )

        db.add(
            AuditLog(
                university_id=trip.university_id,
                action="no_show_penalty",
                entity_type="reservation",
                entity_id=reservation.id,
                description=(
                    "به‌دلیل عدم سوارشدن دانشجو پس از پایان سفر، "
                    "جریمه No-Show ثبت شد."
                ),
                old_values={
                    "no_show_count": old_no_show_count,
                    "negative_score": old_negative_score,
                },
                new_values={
                    "no_show_count": student.no_show_count,
                    "negative_score": student.negative_score,
                    "blocked_until": (
                        student.blocked_until.isoformat()
                        if student.blocked_until is not None
                        else None
                    ),
                },
            )
        )

        penalized_students.append(student)

    db.flush()

    for student in penalized_students:
        create_notification_for_student(
            db,
            student_id=student.id,
            university_id=trip.university_id,
            notification_type="no_show_penalty",
            title="ثبت عدم حضور در سرویس",
            message=(
                "به‌دلیل ثبت رزرو و عدم سوارشدن در سرویس، "
                "امتیاز منفی برای شما ثبت شد."
            ),
            data={
                "trip_id": trip.id,
                "no_show_count": student.no_show_count,
                "negative_score": student.negative_score,
                "blocked_until": (
                    student.blocked_until.isoformat()
                    if student.blocked_until is not None
                    else None
                ),
            },
        )

    return penalized_students


def cancel_pending_boarding_requests(
    db: Session,
    *,
    trip_id: int,
) -> int:
    """
    با پایان سفر، درخواست‌های در انتظار QR و صف انتظار
    دیگر قابل استفاده نیستند و لغو می‌شوند.
    """

    requests = (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.trip_id == trip_id,
            BoardingRequest.status == "pending",
        )
        .all()
    )

    cancelled_count = 0
    now = datetime.now(timezone.utc)

    for request in requests:
        request.status = "cancelled"
        request.responded_at = now
        request.rejection_reason = "سفر به پایان رسید"

        cancelled_count += 1

        create_notification_for_student(
            db,
            student_id=request.student_id,
            university_id=None,
            notification_type="boarding_request_cancelled",
            title="درخواست سوارشدن لغو شد",
            message=(
                "به‌دلیل پایان سفر، درخواست سوارشدن شما "
                "دیگر قابل استفاده نیست."
            ),
            data={
                "boarding_request_id": request.id,
                "trip_id": trip_id,
            },
        )

    return cancelled_count


def notify_reserved_students(
    db: Session,
    *,
    trip: Trip,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> int:
    """اعلان به دانشجویانی که برای این سفر رزرو فعال دارند (بدون commit)."""
    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status == "active",
        )
        .all()
    )
    count = 0
    for reservation in reservations:
        notification = create_notification_for_student(
            db,
            student_id=reservation.student_id,
            university_id=trip.university_id,
            notification_type=notification_type,
            title=title,
            message=message,
            data={"trip_id": trip.id, **(data or {})},
        )
        if notification is not None:
            count += 1
    return count


def announce_trip_delay(
    db: Session,
    *,
    trip: Trip,
    minutes: int,
    reason: str | None,
    reported_by_driver_id: int | None = None,
) -> dict:
    """
    ثبت تأخیر سفر: یک حادثه‌ی نوع trip_delay ثبت می‌شود و دانشجویان رزروکننده
    اعلان می‌گیرند. زمان برنامه‌ریزی‌شده‌ی سفر تغییر نمی‌کند.
    """
    from app.services.trip_incident_service import create_trip_incident

    reason_text = (reason or "").strip()
    incident = create_trip_incident(
        db,
        trip_id=trip.id,
        reported_by_driver_id=reported_by_driver_id,
        incident_type="trip_delay",
        description=f"تأخیر {minutes} دقیقه‌ای" + (f": {reason_text}" if reason_text else ""),
        occurred_at=datetime.now(timezone.utc),
    )

    service_name = trip.service.name if trip.service else ""
    notified = notify_reserved_students(
        db,
        trip=trip,
        notification_type="trip_delay",
        title="تأخیر در سرویس",
        message=f"سرویس «{service_name}» حدود {minutes} دقیقه تأخیر دارد."
        + (f" ({reason_text})" if reason_text else ""),
        data={"delay_minutes": minutes, "incident_id": incident.id},
    )
    db.commit()
    return {"incident_id": incident.id, "notified_students": notified}


def cancel_trip_dependents(
    db: Session,
    *,
    trip: Trip,
) -> dict:
    """
    با لغو سفر: رزروهای فعال/لیست انتظار و درخواست‌های سوارشدن در انتظار
    لغو می‌شوند و به دانشجویان (و راننده) اعلان می‌رود.
    جریمه‌ی عدم‌حضور برای سفر لغوشده ثبت نمی‌شود.
    """
    now = datetime.now(timezone.utc)

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status.in_(["active", "waitlisted"]),
        )
        .all()
    )
    for reservation in reservations:
        reservation.status = "cancelled"
        create_notification_for_student(
            db,
            student_id=reservation.student_id,
            university_id=trip.university_id,
            notification_type="trip_cancelled",
            title="سفر لغو شد",
            message="سفری که برای آن رزرو داشتید لغو شد. رزرو شما به‌صورت خودکار لغو شد.",
            data={"trip_id": trip.id, "reservation_id": reservation.id},
        )

    requests = (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.trip_id == trip.id,
            BoardingRequest.status == "pending",
        )
        .all()
    )
    for request in requests:
        request.status = "cancelled"
        request.responded_at = now
        request.rejection_reason = "سفر لغو شد"
        create_notification_for_student(
            db,
            student_id=request.student_id,
            university_id=trip.university_id,
            notification_type="boarding_request_cancelled",
            title="درخواست سوارشدن لغو شد",
            message="به‌دلیل لغو سفر، درخواست سوارشدن شما لغو شد.",
            data={"boarding_request_id": request.id, "trip_id": trip.id},
        )

    return {"reservations": len(reservations), "boarding_requests": len(requests)}


def complete_trip_if_arrived_at_final_station(
    db: Session,
    *,
    trip_id: int,
    latitude: float,
    longitude: float,
    speed_kmh: float,
    recorded_at: datetime,
):
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        return None

    if trip.status in {"completed", "cancelled"}:
        return None

    if trip.status != "in_progress":
        return None

    if not is_at_final_station(
        db,
        trip_id=trip_id,
        latitude=latitude,
        longitude=longitude,
        speed_kmh=speed_kmh,
    ):
        return None

    trip.status = "completed"
    trip.actual_arrival_time = recorded_at.astimezone(timezone.utc)

    process_trip_no_shows(
        db,
        trip=trip,
    )

    cancel_pending_boarding_requests(
        db,
        trip_id=trip.id,
    )

    db.commit()
    db.refresh(trip)

    try:
        create_low_use_route_notifications(
            db,
            trip_id=trip.id,
            min_completed_trips=LOW_USAGE_MIN_COMPLETED_TRIPS,
            threshold_percent=LOW_USAGE_THRESHOLD_PERCENT,
        )
    except TypeError:
        try:
            create_low_use_route_notifications(
                db,
                trip_id=trip.id,
            )
        except Exception:
            db.rollback()
    except Exception:
        db.rollback()

    return trip