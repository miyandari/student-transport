from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.trip import Trip
from app.models.student import Student
from app.models.trip_passenger import TripPassenger


RESERVATION_STATUSES = {
    "active",
    "cancelled",
}

RESERVABLE_TRIP_STATUSES = {
    "scheduled",
}


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} باید بزرگ‌تر از صفر باشد",
        )


def get_trip(
    db: Session,
    trip_id: int,
) -> Trip:
    validate_positive_id(
        trip_id,
        "شناسه سفر",
    )

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


def get_student(
    db: Session,
    student_id: int,
) -> Student:
    validate_positive_id(
        student_id,
        "شناسه دانشجو",
    )

    student = (
        db.query(Student)
        .filter(Student.id == student_id)
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو پیدا نشد",
        )

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی انتخاب‌شده فعال نیست",
        )

    return student


def validate_trip_for_reservation(
    trip: Trip,
) -> None:
    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )

    if trip.status not in RESERVABLE_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رزرو فقط برای سفرهای برنامه‌ریزی‌شده امکان‌پذیر است",
        )

    if trip.trip_date < datetime.now(timezone.utc).date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای سفر گذشته امکان رزرو وجود ندارد",
        )


def validate_student_for_trip(
    student: Student,
    trip: Trip,
) -> None:
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو و سفر متعلق به یک دانشگاه نیستند",
        )


def get_active_reservation(
    db: Session,
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


def get_onboard_passenger(
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


def count_active_seated_reservations(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(func.count(Reservation.id))
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.status == "active",
            Reservation.is_standing.is_(False),
        )
        .scalar()
        or 0
    )


def count_active_standing_reservations(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(func.count(Reservation.id))
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.status == "active",
            Reservation.is_standing.is_(True),
        )
        .scalar()
        or 0
    )


def validate_reservation_capacity(
    db: Session,
    trip: Trip,
    is_standing: bool,
) -> None:
    if is_standing:
        if not trip.allow_standing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رزرو ایستاده برای این سفر مجاز نیست",
            )

        if trip.standing_capacity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت ایستاده برای این سفر مشخص نشده است",
            )

        if trip.standing_capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت ایستاده این سفر صفر است",
            )

        standing_reserved = count_active_standing_reservations(
            db,
            trip.id,
        )

        if standing_reserved >= trip.standing_capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت رزرو مسافر ایستاده این سفر تکمیل شده است",
            )

    else:
        if trip.seated_capacity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت صندلی برای این سفر مشخص نشده است",
            )

        if trip.seated_capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت صندلی این سفر صفر است",
            )

        seated_reserved = count_active_seated_reservations(
            db,
            trip.id,
        )

        if seated_reserved >= trip.seated_capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت رزرو صندلی این سفر تکمیل شده است",
            )


def create_reservation(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
    is_standing: bool,
) -> Reservation:
    trip = get_trip(
        db,
        trip_id,
    )

    validate_trip_for_reservation(
        trip,
    )

    student = get_student(
        db,
        student_id,
    )

    validate_student_for_trip(
        student,
        trip,
    )

    existing_reservation = get_active_reservation(
        db,
        trip.id,
        student.id,
    )

    if existing_reservation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دانشجو قبلاً برای این سفر رزرو فعال دارد",
        )

    onboard_passenger = get_onboard_passenger(
        db,
        trip.id,
        student.id,
    )

    if onboard_passenger:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دانشجو در حال حاضر در این سفر سوار است و نیازی به رزرو ندارد",
        )

    validate_reservation_capacity(
        db,
        trip,
        is_standing,
    )

    reservation = Reservation(
        trip_id=trip.id,
        student_id=student.id,
        reservation_time=datetime.now(timezone.utc),
        status="active",
        is_standing=is_standing,
    )

    try:
        db.add(reservation)
        db.commit()
        db.refresh(reservation)
    except Exception:
        db.rollback()
        raise

    return reservation


def cancel_reservation(
    db: Session,
    *,
    reservation_id: int,
) -> Reservation:
    validate_positive_id(
        reservation_id,
        "شناسه رزرو",
    )

    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .first()
    )

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رزرو موردنظر پیدا نشد",
        )

    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این رزرو قبلاً لغو شده است",
        )

    if reservation.status not in RESERVATION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وضعیت رزرو نامعتبر است",
        )

    trip = get_trip(
        db,
        reservation.trip_id,
    )

    if trip.status in {
        "completed",
        "cancelled",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رزرو سفر پایان‌یافته یا لغوشده قابل لغو نیست",
        )

    reservation.status = "cancelled"

    try:
        db.commit()
        db.refresh(reservation)
    except Exception:
        db.rollback()
        raise

    return reservation