from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.boarding_request import BoardingRequest
from app.models.driver import Driver
from app.models.reservation import Reservation
from app.models.student import Student
from app.models.station import Station
from app.models.trip import Trip
from app.models.trip_passenger import TripPassenger
from app.models.user import User
from app.services.notification_service import create_notification
from app.services.student_penalty_service import validate_student_not_blocked
from app.services.trip_passenger_service import board_passenger


ACTIVE_TRIP_STATUSES = {"boarding", "in_progress"}

PENDING_STATUS = "pending"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"
CANCELLED_STATUS = "cancelled"


def get_trip(db: Session, trip_id: int) -> Trip:
    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id,
            Trip.is_active.is_(True),
        )
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد.",
        )

    return trip


def get_student(db: Session, student_id: int) -> Student:
    student = (
        db.query(Student)
        .filter(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجوی موردنظر پیدا نشد یا غیرفعال است.",
        )

    return student


def validate_trip_for_boarding_request(
    *,
    trip: Trip,
    student: Student,
) -> None:
    if trip.status not in ACTIVE_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="درخواست سوارشدن فقط برای سفر فعال امکان‌پذیر است.",
        )

    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشجو متعلق به دانشگاه این سفر نیست.",
        )

    if trip.service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس مربوط به این سفر معتبر نیست.",
        )

    restriction = (trip.service.gender_restriction or "mixed").strip().lower()

    if restriction not in {"mixed", "male", "female"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="محدودیت جنسیتی سرویس نامعتبر است.",
        )

    if restriction != "mixed" and student.gender != restriction:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس برای جنسیت دانشجوی انتخاب‌شده مجاز نیست.",
        )

    validate_student_not_blocked(student)


def validate_boarding_station(
    db: Session,
    *,
    trip: Trip,
    station_id: int | None,
) -> Station | None:
    if station_id is None:
        return None

    station = (
        db.query(Station)
        .filter(
            Station.id == station_id,
            Station.is_active.is_(True),
        )
        .first()
    )

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه موردنظر پیدا نشد یا غیرفعال است.",
        )

    if station.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ایستگاه متعلق به دانشگاه این سفر نیست.",
        )

    if trip.service is None or trip.service.route is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر مربوط به این سفر معتبر نیست.",
        )

    from app.models.route_station import RouteStation

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == trip.service.route.id,
            RouteStation.station_id == station.id,
        )
        .first()
    )

    if route_station is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ایستگاه انتخاب‌شده در مسیر این سفر قرار ندارد.",
        )

    return station


def get_active_reservation(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
) -> Reservation | None:
    return (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.student_id == student_id,
            Reservation.status == "active",
        )
        .first()
    )


def get_active_boarding_request(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
) -> BoardingRequest | None:
    return (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.trip_id == trip_id,
            BoardingRequest.student_id == student_id,
            BoardingRequest.status == PENDING_STATUS,
        )
        .order_by(BoardingRequest.id.desc())
        .first()
    )


def get_active_trip_passenger(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
) -> TripPassenger | None:
    return (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip_id,
            TripPassenger.student_id == student_id,
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
        )
        .first()
    )


def get_driver_user(
    db: Session,
    *,
    trip: Trip,
) -> User | None:
    if trip.driver_id is None:
        return None

    driver = (
        db.query(Driver)
        .filter(Driver.id == trip.driver_id)
        .first()
    )

    if driver is None:
        return None

    return (
        db.query(User)
        .filter(
            User.driver_id == driver.id,
            User.is_active.is_(True),
        )
        .first()
    )


def get_trip_capacity(
    db: Session,
    *,
    trip: Trip,
) -> tuple[int, int]:
    passengers = (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip.id,
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
        )
        .all()
    )

    seated_count = sum(
        1
        for passenger in passengers
        if not passenger.is_standing
    )

    standing_count = sum(
        1
        for passenger in passengers
        if passenger.is_standing
    )

    return seated_count, standing_count


def get_available_boarding_mode(
    db: Session,
    *,
    trip: Trip,
    requested_is_standing: bool,
) -> bool | None:
    """
    تعیین می‌کند درخواست با چه حالتی می‌تواند سوار شود:

    False = نشسته
    True = ایستاده
    None = هیچ ظرفیتی وجود ندارد

    برای درخواست عادی که حالت ایستاده را مشخص نکرده باشد،
    ابتدا صندلی بررسی می‌شود و در صورت تکمیل صندلی‌ها،
    ظرفیت ایستاده بررسی خواهد شد.
    """

    seated_count, standing_count = get_trip_capacity(
        db,
        trip=trip,
    )

    seated_capacity = trip.seated_capacity or 0
    standing_capacity = trip.standing_capacity or 0

    if requested_is_standing:
        if (
            trip.allow_standing
            and standing_count < standing_capacity
        ):
            return True

        return None

    if seated_count < seated_capacity:
        return False

    if (
        trip.allow_standing
        and standing_count < standing_capacity
    ):
        return True

    return None


def has_available_capacity(
    db: Session,
    *,
    trip: Trip,
    is_standing: bool,
) -> bool:
    return (
        get_available_boarding_mode(
            db,
            trip=trip,
            requested_is_standing=is_standing,
        )
        is not None
    )


def create_boarding_request(
    db: Session,
    *,
    student_id: int,
    trip_id: int,
    boarding_station_id: int | None = None,
    is_standing: bool = False,
    requires_driver_approval: bool = False,
) -> BoardingRequest:
    student = get_student(db, student_id)
    trip = get_trip(db, trip_id)

    validate_trip_for_boarding_request(
        trip=trip,
        student=student,
    )

    validate_boarding_station(
        db,
        trip=trip,
        station_id=boarding_station_id,
    )

    passenger = get_active_trip_passenger(
        db,
        trip_id=trip_id,
        student_id=student_id,
    )

    if passenger is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو قبلاً در این سفر سوار شده است.",
        )

    reservation = get_active_reservation(
        db,
        trip_id=trip_id,
        student_id=student_id,
    )

    if reservation is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سفر رزرو فعال دارید. برای سوارشدن نیازی به درخواست جدید نیست.",
        )

    pending_request = get_active_boarding_request(
        db,
        trip_id=trip_id,
        student_id=student_id,
    )

    if pending_request is not None:
        return pending_request

    now = datetime.now(timezone.utc)

    # درخواست QR همیشه باید توسط راننده تأیید شود.
    if requires_driver_approval:
        request = BoardingRequest(
            trip_id=trip.id,
            student_id=student.id,
            boarding_station_id=boarding_station_id,
            is_standing=is_standing,
            requires_driver_approval=True,
            status=PENDING_STATUS,
            requested_at=now,
        )

        db.add(request)
        db.flush()

        driver_user = get_driver_user(
            db,
            trip=trip,
        )

        if driver_user is not None:
            create_notification(
                db,
                user_id=driver_user.id,
                university_id=trip.university_id,
                notification_type="boarding_request_driver_approval",
                title="درخواست سوارشدن جدید",
                message=(
                    "یک دانشجو از طریق QR ایستگاه درخواست سوارشدن داده است. "
                    "لطفاً درخواست را بررسی کنید."
                ),
                data={
                    "boarding_request_id": request.id,
                    "trip_id": trip.id,
                    "student_id": student.id,
                    "boarding_station_id": boarding_station_id,
                    "is_standing": is_standing,
                },
            )

        create_notification_for_student(
            db,
            student_id=student.id,
            university_id=student.university_id,
            notification_type="boarding_request_pending",
            title="درخواست سوارشدن ارسال شد",
            message="درخواست سوارشدن شما برای بررسی راننده ارسال شد.",
            data={
                "boarding_request_id": request.id,
                "trip_id": trip.id,
                "boarding_station_id": boarding_station_id,
                "requires_driver_approval": True,
            },
        )

        db.commit()
        db.refresh(request)

        return request

    # درخواست عادی دانشجو:
    # اگر صندلی موجود باشد، نشسته ثبت می‌شود.
    # اگر صندلی پر باشد ولی ظرفیت ایستاده وجود داشته باشد،
    # به‌صورت ایستاده ثبت می‌شود.
    # در غیر این صورت وارد صف انتظار می‌شود.
    boarding_mode = get_available_boarding_mode(
        db,
        trip=trip,
        requested_is_standing=is_standing,
    )

    if boarding_mode is not None:
        boarded_passenger = board_passenger(
            db,
            trip_id=trip.id,
            student_id=student.id,
            boarding_method="automatic_request",
            is_standing=boarding_mode,
            boarding_station_id=boarding_station_id,
        )

        request = BoardingRequest(
            trip_id=trip.id,
            student_id=student.id,
            boarding_station_id=boarding_station_id,
            is_standing=boarded_passenger.is_standing,
            requires_driver_approval=False,
            status=APPROVED_STATUS,
            requested_at=now,
            responded_at=now,
            responded_by_user_id=None,
            rejection_reason=None,
        )

        db.add(request)
        db.flush()

        create_notification_for_student(
            db,
            student_id=student.id,
            university_id=student.university_id,
            notification_type="boarding_request_approved",
            title="درخواست سوارشدن تأیید شد",
            message="درخواست سوارشدن شما به‌صورت خودکار تأیید و سوارشدن شما ثبت شد.",
            data={
                "boarding_request_id": request.id,
                "trip_id": trip.id,
                "trip_passenger_id": boarded_passenger.id,
                "is_standing": boarded_passenger.is_standing,
                "boarding_method": "automatic_request",
            },
        )

        db.commit()
        db.refresh(request)

        return request

    # ظرفیت صندلی و ایستاده هر دو تکمیل است؛
    # درخواست عادی وارد صف انتظار می‌شود و برای راننده ارسال نمی‌شود.
    request = BoardingRequest(
        trip_id=trip.id,
        student_id=student.id,
        boarding_station_id=boarding_station_id,
        is_standing=is_standing,
        requires_driver_approval=False,
        status=PENDING_STATUS,
        requested_at=now,
    )

    db.add(request)
    db.flush()

    create_notification_for_student(
        db,
        student_id=student.id,
        university_id=student.university_id,
        notification_type="boarding_request_waitlist",
        title="درخواست سوارشدن در صف انتظار قرار گرفت",
        message=(
            "ظرفیت مجاز سرویس در حال حاضر تکمیل است. "
            "درخواست شما در صف انتظار قرار گرفت."
        ),
        data={
            "boarding_request_id": request.id,
            "trip_id": trip.id,
            "student_id": student.id,
            "boarding_station_id": boarding_station_id,
            "is_standing": is_standing,
            "requires_driver_approval": False,
        },
    )

    db.commit()
    db.refresh(request)

    return request


def get_pending_boarding_requests(
    db: Session,
    *,
    trip_id: int,
) -> list[BoardingRequest]:
    get_trip(db, trip_id)

    return (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.trip_id == trip_id,
            BoardingRequest.status == PENDING_STATUS,
            BoardingRequest.requires_driver_approval.is_(True),
        )
        .order_by(BoardingRequest.requested_at.asc())
        .all()
    )


def approve_boarding_request(
    db: Session,
    *,
    request_id: int,
    responded_by_user_id: int,
) -> BoardingRequest:
    request = (
        db.query(BoardingRequest)
        .filter(BoardingRequest.id == request_id)
        .first()
    )

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="درخواست سوارشدن پیدا نشد.",
        )

    if request.status != PENDING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این درخواست قبلاً تعیین‌تکلیف شده است.",
        )

    if not request.requires_driver_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این درخواست نیازی به تأیید راننده ندارد.",
        )

    trip = get_trip(db, request.trip_id)
    student = get_student(db, request.student_id)

    validate_trip_for_boarding_request(
        trip=trip,
        student=student,
    )

    passenger = get_active_trip_passenger(
        db,
        trip_id=trip.id,
        student_id=student.id,
    )

    if passenger is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو قبلاً در این سفر سوار شده است.",
        )

    boarding_mode = get_available_boarding_mode(
        db,
        trip=trip,
        requested_is_standing=request.is_standing,
    )

    if boarding_mode is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ظرفیت سرویس هنوز تکمیل است.",
        )

    boarded_passenger = board_passenger(
        db,
        trip_id=trip.id,
        student_id=student.id,
        boarding_method="driver_approved",
        is_standing=boarding_mode,
        boarding_station_id=request.boarding_station_id,
    )

    request.status = APPROVED_STATUS
    request.responded_at = datetime.now(timezone.utc)
    request.responded_by_user_id = responded_by_user_id
    request.rejection_reason = None
    request.is_standing = boarded_passenger.is_standing

    db.add(request)

    create_notification_for_student(
        db,
        student_id=student.id,
        university_id=student.university_id,
        notification_type="boarding_request_approved",
        title="درخواست سوارشدن تأیید شد",
        message="درخواست سوارشدن شما تأیید و سوارشدن شما ثبت شد.",
        data={
            "boarding_request_id": request.id,
            "trip_id": trip.id,
            "trip_passenger_id": boarded_passenger.id,
            "is_standing": boarded_passenger.is_standing,
            "boarding_method": "driver_approved",
        },
    )

    db.commit()
    db.refresh(request)

    return request


def reject_boarding_request(
    db: Session,
    *,
    request_id: int,
    responded_by_user_id: int,
    rejection_reason: str | None = None,
) -> BoardingRequest:
    request = (
        db.query(BoardingRequest)
        .filter(BoardingRequest.id == request_id)
        .first()
    )

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="درخواست سوارشدن پیدا نشد.",
        )

    if request.status != PENDING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این درخواست قبلاً تعیین‌تکلیف شده است.",
        )

    if not request.requires_driver_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این درخواست نیازی به تأیید راننده ندارد.",
        )

    trip = get_trip(db, request.trip_id)
    student = get_student(db, request.student_id)

    if trip.status not in ACTIVE_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سفر دیگر فعال نیست.",
        )

    request.status = REJECTED_STATUS
    request.responded_at = datetime.now(timezone.utc)
    request.responded_by_user_id = responded_by_user_id
    request.rejection_reason = rejection_reason

    db.add(request)

    create_notification_for_student(
        db,
        student_id=student.id,
        university_id=student.university_id,
        notification_type="boarding_request_rejected",
        title="درخواست سوارشدن رد شد",
        message=(
            "درخواست سوارشدن شما رد شد."
            + (
                f" دلیل: {rejection_reason}"
                if rejection_reason
                else ""
            )
        ),
        data={
            "boarding_request_id": request.id,
            "trip_id": trip.id,
            "rejection_reason": rejection_reason,
        },
    )

    db.commit()
    db.refresh(request)

    return request


def cancel_boarding_request(
    db: Session,
    *,
    request_id: int,
    student_id: int,
) -> BoardingRequest:
    request = (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.id == request_id,
            BoardingRequest.student_id == student_id,
        )
        .first()
    )

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="درخواست سوارشدن پیدا نشد.",
        )

    if request.status != PENDING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فقط درخواست‌های در انتظار قابل لغو هستند.",
        )

    request.status = CANCELLED_STATUS
    request.responded_at = datetime.now(timezone.utc)

    db.add(request)
    db.commit()
    db.refresh(request)

    return request


def create_notification_for_student(
    db: Session,
    *,
    student_id: int,
    university_id: int | None,
    notification_type: str,
    title: str,
    message: str,
    data: dict | None = None,
) -> None:
    user = (
        db.query(User)
        .filter(
            User.student_id == student_id,
            User.is_active.is_(True),
        )
        .first()
    )

    if user is None:
        return

    create_notification(
        db,
        user_id=user.id,
        university_id=university_id,
        notification_type=notification_type,
        title=title,
        message=message,
        data=data,
    )