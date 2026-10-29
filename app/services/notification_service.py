from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.models.trip import Trip
from app.models.reservation import Reservation
from app.models.route import Route
from app.models.service import Service
from app.core.roles import Roles


NEAR_STATION_NOTIFICATION_MINUTES = 2
NOTIFICATION_DUPLICATE_WINDOW_MINUTES = 10

DEMAND_THRESHOLD = 10

LOW_USAGE_MIN_COMPLETED_TRIPS = 5
LOW_USAGE_THRESHOLD_PERCENT = 30


def create_notification(
    db: Session,
    *,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    university_id: int | None = None,
    transport_company_id: int | None = None,
    data: dict | None = None,
):
    notification = Notification(
        user_id=user_id,
        university_id=university_id,
        transport_company_id=transport_company_id,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data,
        is_read=False,
    )

    db.add(notification)
    db.flush()

    return notification


def create_notification_for_student(
    db: Session,
    *,
    student_id: int,
    notification_type: str,
    title: str,
    message: str,
    university_id: int | None = None,
    transport_company_id: int | None = None,
    data: dict | None = None,
):
    user = (
        db.query(User)
        .filter(
            User.student_id == student_id,
            User.is_active.is_(True),
        )
        .first()
    )

    if user is None:
        return None

    return create_notification(
        db,
        user_id=user.id,
        university_id=university_id,
        transport_company_id=transport_company_id,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data,
    )


def create_near_station_notifications(
    db: Session,
    *,
    trip_id: int,
    station_id: int,
    station_name: str,
    stop_order: int,
    eta_seconds: float,
    reservations,
):
    if eta_seconds < 0:
        return 0

    if eta_seconds > NEAR_STATION_NOTIFICATION_MINUTES * 60:
        return 0

    now = datetime.now(timezone.utc)

    duplicate_since = now - timedelta(
        minutes=NOTIFICATION_DUPLICATE_WINDOW_MINUTES
    )

    created_count = 0

    for reservation, user in reservations:

        if not user.is_active:
            continue

        recent_notifications = (
            db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.notification_type
                == "trip_near_station",
                Notification.created_at >= duplicate_since,
            )
            .all()
        )

        duplicate = False

        for notification in recent_notifications:

            data = notification.data or {}

            if (
                data.get("trip_id") == trip_id
                and data.get("station_id") == station_id
            ):
                duplicate = True
                break

        if duplicate:
            continue

        eta_minutes = max(
            1,
            round(eta_seconds / 60),
        )

        create_notification(
            db,
            user_id=user.id,
            university_id=user.university_id,
            notification_type="trip_near_station",
            title="سرویس در حال نزدیک‌شدن است",
            message=(
                f"سرویس شما حدود {eta_minutes} دقیقه "
                f"تا ایستگاه «{station_name}» فاصله دارد."
            ),
            data={
                "trip_id": trip_id,
                "reservation_id": reservation.id,
                "station_id": station_id,
                "station_name": station_name,
                "stop_order": stop_order,
                "eta_seconds": eta_seconds,
            },
        )

        created_count += 1

    if created_count > 0:
        db.commit()

    return created_count


def create_demand_threshold_notifications(
    db: Session,
    *,
    trip: Trip,
    active_reservation_count: int,
) -> int:

    if active_reservation_count <= DEMAND_THRESHOLD:
        return 0

    now = datetime.now(timezone.utc)

    duplicate_since = now - timedelta(
        minutes=NOTIFICATION_DUPLICATE_WINDOW_MINUTES
    )

    management_roles = {
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
    }

    query = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            (
                (
                    User.university_id == trip.university_id
                )
                & User.role.in_(management_roles)
            )
            | (User.role == Roles.SUPER_ADMIN),
        )
    )

    users = query.all()

    created_count = 0

    for user in users:

        recent_notifications = (
            db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.notification_type
                == "trip_demand_threshold",
                Notification.created_at >= duplicate_since,
            )
            .all()
        )

        duplicate = False

        for notification in recent_notifications:

            data = notification.data or {}

            if data.get("trip_id") == trip.id:
                duplicate = True
                break

        if duplicate:
            continue

        create_notification(
            db,
            user_id=user.id,
            university_id=trip.university_id,
            notification_type="trip_demand_threshold",
            title="نیاز به بررسی افزایش ظرفیت سرویس",
            message=(
                f"تعداد درخواست‌های فعال سفر شماره {trip.id} "
                f"به {active_reservation_count} نفر رسیده است. "
                "پیشنهاد می‌شود امکان اختصاص خودروی اضافه بررسی شود."
            ),
            data={
                "trip_id": trip.id,
                "university_id": trip.university_id,
                "active_reservation_count": active_reservation_count,
                "threshold": DEMAND_THRESHOLD,
                "action": "consider_additional_vehicle",
            },
        )

        created_count += 1

    if created_count > 0:
        db.commit()

    return created_count


def create_low_use_route_notifications(
    db: Session,
    *,
    route_id: int,
) -> int:
    route = (
        db.query(Route)
        .filter(Route.id == route_id)
        .first()
    )

    if route is None:
        return 0

    completed_trips = (
        db.query(Trip)
        .join(
            Service,
            Service.id == Trip.service_id,
        )
        .filter(
            Service.route_id == route.id,
            Trip.university_id == route.university_id,
            Trip.status == "completed",
            Trip.is_active.is_(True),
            Trip.seated_capacity.isnot(None),
            Trip.seated_capacity > 0,
        )
        .order_by(
            Trip.trip_date.desc(),
            Trip.id.desc(),
        )
        .limit(LOW_USAGE_MIN_COMPLETED_TRIPS)
        .all()
    )

    if len(completed_trips) < LOW_USAGE_MIN_COMPLETED_TRIPS:
        return 0

    trip_ids = [
        trip.id
        for trip in completed_trips
    ]

    reservation_counts = dict(
        db.query(
            Reservation.trip_id,
            func.count(Reservation.id),
        )
        .filter(
            Reservation.trip_id.in_(trip_ids),
            Reservation.status == "active",
            Reservation.is_standing.is_(False),
        )
        .group_by(
            Reservation.trip_id,
        )
        .all()
    )

    total_capacity = sum(
        trip.seated_capacity or 0
        for trip in completed_trips
    )

    total_reserved = sum(
        reservation_counts.get(trip.id, 0)
        for trip in completed_trips
    )

    if total_capacity <= 0:
        return 0

    usage_percent = (
        total_reserved / total_capacity
    ) * 100

    if usage_percent >= LOW_USAGE_THRESHOLD_PERCENT:
        return 0

    now = datetime.now(timezone.utc)

    duplicate_since = now - timedelta(
        minutes=NOTIFICATION_DUPLICATE_WINDOW_MINUTES
    )

    management_roles = {
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
    }

    users = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            (
                (
                    User.university_id == route.university_id
                )
                & User.role.in_(management_roles)
            )
            | (User.role == Roles.SUPER_ADMIN),
        )
        .all()
    )

    created_count = 0

    for user in users:

        recent_notifications = (
            db.query(Notification)
            .filter(
                Notification.user_id == user.id,
                Notification.notification_type
                == "low_use_route",
                Notification.created_at >= duplicate_since,
            )
            .all()
        )

        duplicate = False

        for notification in recent_notifications:

            data = notification.data or {}

            if data.get("route_id") == route.id:
                duplicate = True
                break

        if duplicate:
            continue

        create_notification(
            db,
            user_id=user.id,
            university_id=route.university_id,
            notification_type="low_use_route",
            title="مسیر کم‌استفاده شناسایی شد",
            message=(
                f"مسیر «{route.name}» در "
                f"{len(completed_trips)} سفر اخیر، "
                f"به‌طور میانگین فقط {usage_percent:.1f}٪ "
                "ظرفیت صندلی خود را استفاده کرده است. "
                "پیشنهاد می‌شود میزان استفاده و امکان اصلاح "
                "یا تغییر مسیر بررسی شود."
            ),
            data={
                "route_id": route.id,
                "route_name": route.name,
                "university_id": route.university_id,
                "completed_trip_count": len(completed_trips),
                "total_capacity": total_capacity,
                "total_reserved": total_reserved,
                "usage_percent": round(
                    usage_percent,
                    2,
                ),
                "threshold_percent": LOW_USAGE_THRESHOLD_PERCENT,
                "action": "review_route",
            },
        )

        created_count += 1

    if created_count > 0:
        db.commit()

    return created_count


def get_user_notifications(
    db: Session,
    *,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
):
    query = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
        )
    )

    if unread_only:
        query = query.filter(
            Notification.is_read.is_(False),
        )

    return (
        query
        .order_by(
            Notification.created_at.desc(),
        )
        .limit(limit)
        .all()
    )


def mark_notification_as_read(
    db: Session,
    *,
    notification_id: int,
    user_id: int,
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .first()
    )

    if notification is None:
        return None

    if not notification.is_read:

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(notification)

    return notification


def mark_all_notifications_as_read(
    db: Session,
    *,
    user_id: int,
) -> int:

    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .all()
    )

    if not notifications:
        return 0

    read_at = datetime.now(timezone.utc)

    for notification in notifications:

        notification.is_read = True
        notification.read_at = read_at

    db.commit()

    return len(notifications)


def get_unread_notification_count(
    db: Session,
    *,
    user_id: int,
) -> int:

    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .count()
    )