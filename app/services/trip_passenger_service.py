from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trip_passenger import TripPassenger
from app.models.trip import Trip
from app.models.student import Student
from app.models.station import Station
from app.models.route_station import RouteStation


ACTIVE_TRIP_STATUSES = {
    "boarding",
    "in_progress",
}

ALLOWED_GENDER_RESTRICTIONS = {
    "mixed",
    "male",
    "female",
}


def get_trip(
    db: Session,
    trip_id: int,
    *,
    for_update: bool = False,
) -> Trip:
    query = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id,
            Trip.is_active.is_(True),
        )
    )

    if for_update:
        query = query.with_for_update()

    trip = query.first()

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    return trip


def validate_trip_for_boarding(
    trip: Trip,
) -> None:
    if trip.status not in ACTIVE_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="در وضعیت فعلی سفر، امکان ثبت سوارشدن مسافر وجود ندارد",
        )


def get_student(
    db: Session,
    student_id: int,
) -> Student:
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
            detail="دانشجوی موردنظر پیدا نشد یا غیرفعال است",
        )

    return student


def validate_student_access(
    student: Student,
    trip: Trip,
) -> None:
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشجو متعلق به دانشگاه این سفر نیست",
        )


def validate_gender_restriction(
    student: Student,
    trip: Trip,
) -> None:
    if trip.service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس مربوط به این سفر معتبر نیست",
        )

    restriction = (
        trip.service.gender_restriction or "mixed"
    ).strip().lower()

    if restriction not in ALLOWED_GENDER_RESTRICTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="محدودیت جنسیتی سرویس نامعتبر است",
        )

    if restriction == "mixed":
        return

    if student.gender != restriction:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس برای جنسیت دانشجوی انتخاب‌شده مجاز نیست",
        )


def get_active_passenger(
    db: Session,
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


def validate_duplicate_boarding(
    db: Session,
    trip_id: int,
    student_id: int,
) -> None:
    active_passenger = get_active_passenger(
        db=db,
        trip_id=trip_id,
        student_id=student_id,
    )

    if active_passenger is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این دانشجو در این سفر قبلاً سوار شده است",
        )


def validate_station_for_trip(
    db: Session,
    trip: Trip,
    station_id: int,
    field_name: str,
) -> Station:
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
            detail=f"{field_name} موردنظر پیدا نشد یا غیرفعال است",
        )

    if station.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{field_name} متعلق به دانشگاه این سفر نیست",
        )

    if trip.service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس مربوط به این سفر معتبر نیست",
        )

    route = trip.service.route

    if route is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر مربوط به این سرویس معتبر نیست",
        )

    if route.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مسیر سرویس متعلق به این دانشگاه نیست",
        )

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == route.id,
            RouteStation.station_id == station.id,
        )
        .first()
    )

    if route_station is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} در مسیر این سفر قرار ندارد",
        )

    return station


def count_onboard_seated_passengers(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip_id,
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
            TripPassenger.is_standing.is_(False),
        )
        .count()
    )


def count_onboard_standing_passengers(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip_id,
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
            TripPassenger.is_standing.is_(True),
        )
        .count()
    )


def get_available_boarding_mode(
    db: Session,
    trip: Trip,
    requested_is_standing: bool,
) -> bool | None:
    seated_count = count_onboard_seated_passengers(
        db,
        trip.id,
    )

    standing_count = count_onboard_standing_passengers(
        db,
        trip.id,
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


def validate_passenger_capacity(
    db: Session,
    trip: Trip,
    is_standing: bool,
) -> None:
    if is_standing:
        if not trip.allow_standing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ایستادن در این سفر مجاز نیست",
            )

        current_standing = count_onboard_standing_passengers(
            db=db,
            trip_id=trip.id,
        )

        if (
            trip.standing_capacity is not None
            and current_standing >= trip.standing_capacity
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="ظرفیت مسافران ایستاده تکمیل شده است",
            )

        return

    current_seated = count_onboard_seated_passengers(
        db=db,
        trip_id=trip.id,
    )

    if (
        trip.seated_capacity is not None
        and current_seated >= trip.seated_capacity
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ظرفیت صندلی‌های این سفر تکمیل شده است",
        )


def create_trip_passenger(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
    boarding_method: str,
    is_standing: bool,
    boarding_station_id: int | None,
    alighting_station_id: int | None,
) -> TripPassenger:

    trip = get_trip(
        db,
        trip_id,
        for_update=True,
    )

    validate_trip_for_boarding(trip)

    student = get_student(
        db,
        student_id,
    )

    validate_student_access(
        student,
        trip,
    )

    validate_gender_restriction(
        student,
        trip,
    )

    validate_duplicate_boarding(
        db,
        trip.id,
        student.id,
    )

    if boarding_station_id is not None:
        validate_station_for_trip(
            db,
            trip,
            boarding_station_id,
            "ایستگاه سوارشدن",
        )

    if alighting_station_id is not None:
        validate_station_for_trip(
            db,
            trip,
            alighting_station_id,
            "ایستگاه پیاده‌شدن",
        )

    validate_passenger_capacity(
        db,
        trip,
        is_standing,
    )

    passenger = TripPassenger(
        trip_id=trip.id,
        student_id=student.id,
        boarding_time=datetime.now(timezone.utc),
        boarding_station_id=boarding_station_id,
        boarding_method=boarding_method,
        is_standing=is_standing,
        alighting_station_id=alighting_station_id,
    )

    db.add(passenger)
    db.commit()
    db.refresh(passenger)

    return passenger


def board_passenger(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
    boarding_method: str,
    is_standing: bool,
    boarding_station_id: int | None,
) -> TripPassenger:

    trip = get_trip(
        db,
        trip_id,
        for_update=True,
    )

    validate_trip_for_boarding(trip)

    student = get_student(
        db,
        student_id,
    )

    validate_student_access(
        student,
        trip,
    )

    validate_gender_restriction(
        student,
        trip,
    )

    validate_duplicate_boarding(
        db,
        trip.id,
        student.id,
    )

    if boarding_station_id is not None:
        validate_station_for_trip(
            db,
            trip,
            boarding_station_id,
            "ایستگاه سوارشدن",
        )

    validate_passenger_capacity(
        db,
        trip,
        is_standing,
    )

    passenger = TripPassenger(
        trip_id=trip.id,
        student_id=student.id,
        boarding_time=datetime.now(timezone.utc),
        boarding_station_id=boarding_station_id,
        boarding_method=boarding_method,
        is_standing=is_standing,
    )

    db.add(passenger)
    db.commit()
    db.refresh(passenger)

    return passenger


def validate_waitlist_capacity(
    db: Session,
    trip: Trip,
    is_standing: bool,
) -> bool:
    return (
        get_available_boarding_mode(
            db,
            trip,
            is_standing,
        )
        is not None
    )


def create_waitlist_promotion_notification(
    db: Session,
    *,
    student_id: int,
    trip: Trip,
    request,
    passenger: TripPassenger,
) -> None:
    from app.models.user import User
    from app.services.notification_service import create_notification

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
        university_id=trip.university_id,
        notification_type="boarding_request_waitlist_promoted",
        title="درخواست صف انتظار تأیید شد",
        message=(
            "با آزادشدن ظرفیت، درخواست شما به‌صورت خودکار "
            "تأیید و سوارشدن ثبت شد."
        ),
        data={
            "boarding_request_id": request.id,
            "trip_id": trip.id,
            "trip_passenger_id": passenger.id,
            "boarding_method": "automatic_waitlist",
            "is_standing": passenger.is_standing,
        },
    )


def promote_waitlisted_boarding_requests(
    db: Session,
    *,
    trip_id: int,
) -> list[TripPassenger]:
    from app.models.boarding_request import BoardingRequest

    trip = get_trip(
        db,
        trip_id,
        for_update=True,
    )

    validate_trip_for_boarding(trip)

    requests = (
        db.query(BoardingRequest)
        .filter(
            BoardingRequest.trip_id == trip.id,
            BoardingRequest.status == "pending",
            BoardingRequest.requires_driver_approval.is_(False),
        )
        .order_by(
            BoardingRequest.requested_at.asc(),
            BoardingRequest.id.asc(),
        )
        .all()
    )

    promoted_passengers: list[TripPassenger] = []

    for request in requests:
        student = get_student(
            db,
            request.student_id,
        )

        validate_student_access(
            student,
            trip,
        )

        validate_gender_restriction(
            student,
            trip,
        )

        if get_active_passenger(
            db,
            trip.id,
            student.id,
        ) is not None:
            request.status = "cancelled"
            request.responded_at = datetime.now(timezone.utc)
            continue

        actual_is_standing = get_available_boarding_mode(
            db,
            trip,
            request.is_standing,
        )

        if actual_is_standing is None:
            break

        passenger = TripPassenger(
            trip_id=trip.id,
            student_id=student.id,
            boarding_time=datetime.now(timezone.utc),
            boarding_station_id=request.boarding_station_id,
            boarding_method="automatic_waitlist",
            is_standing=actual_is_standing,
        )

        db.add(passenger)
        db.flush()

        request.status = "approved"
        request.responded_at = datetime.now(timezone.utc)
        request.responded_by_user_id = None
        request.rejection_reason = None
        request.is_standing = actual_is_standing

        create_waitlist_promotion_notification(
            db,
            student_id=student.id,
            trip=trip,
            request=request,
            passenger=passenger,
        )

        promoted_passengers.append(passenger)

    db.commit()

    for passenger in promoted_passengers:
        db.refresh(passenger)

    return promoted_passengers


def alight_passenger(
    db: Session,
    *,
    passenger_id: int,
    alighting_station_id: int | None,
) -> TripPassenger:

    passenger = (
        db.query(TripPassenger)
        .filter(
            TripPassenger.id == passenger_id,
        )
        .first()
    )

    if passenger is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رکورد مسافر پیدا نشد",
        )

    if passenger.boarding_time is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این مسافر زمان سوارشدن ثبت نشده است",
        )

    if passenger.alighting_time is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="پیاده‌شدن این مسافر قبلاً ثبت شده است",
        )

    trip = get_trip(
        db,
        passenger.trip_id,
    )

    if alighting_station_id is not None:
        validate_station_for_trip(
            db,
            trip,
            alighting_station_id,
            "ایستگاه پیاده‌شدن",
        )

    passenger.alighting_time = datetime.now(timezone.utc)
    passenger.alighting_station_id = alighting_station_id

    db.commit()

    promote_waitlisted_boarding_requests(
        db,
        trip_id=passenger.trip_id,
    )

    db.refresh(passenger)

    return passenger