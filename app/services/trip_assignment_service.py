from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.trip import Trip
from app.models.trip_assignment import TripAssignment


def get_active_assignment(
    db: Session,
    trip_id: int,
):
    """
    آخرین تخصیص فعال سفر را برمی‌گرداند.

    در هر لحظه باید حداکثر یک تخصیص فعال برای هر سفر وجود داشته باشد.
    """

    return (
        db.query(TripAssignment)
        .filter(
            TripAssignment.trip_id == trip_id,
            TripAssignment.is_active.is_(True),
        )
        .order_by(
            TripAssignment.start_at.desc().nullslast(),
            TripAssignment.id.desc(),
        )
        .first()
    )


def sync_trip_with_assignment(
    db: Session,
    trip: Trip,
    assignment: TripAssignment,
):
    """
    وضعیت فعلی سفر را دقیقاً با تخصیص فعال هماهنگ می‌کند.

    توجه:
    اگر تخصیص فقط راننده داشته باشد، خودرو قبلی Trip حذف می‌شود.
    اگر تخصیص فقط خودرو داشته باشد، راننده قبلی Trip حذف می‌شود.

    بنابراین Trip همیشه بازتاب‌دهنده دقیق تخصیص فعال است.
    """

    trip.driver_id = assignment.driver_id
    trip.vehicle_id = assignment.vehicle_id

    db.flush()

    return trip


def activate_assignment(
    db: Session,
    assignment: TripAssignment,
):
    """
    یک تخصیص را فعال می‌کند.

    اگر تخصیص دیگری برای همان سفر فعال باشد،
    ابتدا آن تخصیص غیرفعال می‌شود.
    """

    trip = (
        db.query(Trip)
        .filter(
            Trip.id == assignment.trip_id,
        )
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر مرتبط با تخصیص پیدا نشد",
        )

    if (
        assignment.driver_id is None
        and assignment.vehicle_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "برای فعال‌سازی تخصیص، حداقل راننده "
                "یا خودرو باید مشخص باشد"
            ),
        )

    current_assignment = get_active_assignment(
        db,
        trip.id,
    )

    if (
        current_assignment is not None
        and current_assignment.id != assignment.id
    ):
        current_assignment.is_active = False

    assignment.is_active = True

    sync_trip_with_assignment(
        db,
        trip,
        assignment,
    )

    db.flush()

    return assignment


def deactivate_assignment(
    db: Session,
    assignment: TripAssignment,
):
    """
    تخصیص را غیرفعال می‌کند.

    اگر این تخصیص یک جایگزین باشد و به تخصیص قبلی
    اشاره کند، همان تخصیص قبلی دوباره فعال می‌شود.

    به این ترتیب زنجیره‌ای مانند:

    A → B → C

    می‌تواند به شکل صحیح به:

    C → B → A

    برگردد.
    """

    trip = (
        db.query(Trip)
        .filter(
            Trip.id == assignment.trip_id,
        )
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر مرتبط با تخصیص پیدا نشد",
        )

    assignment.is_active = False

    db.flush()

    # اگر این تخصیص جایگزین تخصیص دیگری بوده است،
    # دقیقاً همان تخصیص قبلی را پیدا می‌کنیم.
    if assignment.replaces_assignment_id is not None:

        previous_assignment = (
            db.query(TripAssignment)
            .filter(
                TripAssignment.id
                == assignment.replaces_assignment_id,
                TripAssignment.trip_id
                == assignment.trip_id,
            )
            .first()
        )

        if previous_assignment is not None:

            previous_assignment.is_active = True

            sync_trip_with_assignment(
                db,
                trip,
                previous_assignment,
            )

            db.flush()

            return assignment

    # اگر تخصیص اصلی بوده یا تخصیص قبلی وجود نداشته،
    # منابع فعلی سفر پاک می‌شوند.
    trip.driver_id = None
    trip.vehicle_id = None

    db.flush()

    return assignment


def replace_active_assignment(
    db: Session,
    trip: Trip,
    new_assignment: TripAssignment,
):
    """
    تخصیص فعال فعلی را با تخصیص جدید جایگزین می‌کند.

    اگر تخصیص جدید از نوع substitute باشد و
    replaces_assignment_id مشخص نشده باشد،
    تخصیص فعال فعلی به‌عنوان تخصیص جایگزین‌شده ثبت می‌شود.
    """

    current_assignment = get_active_assignment(
        db,
        trip.id,
    )

    if (
        new_assignment.assignment_type == "substitute"
        and new_assignment.replaces_assignment_id is None
        and current_assignment is not None
        and current_assignment.id != new_assignment.id
    ):
        new_assignment.replaces_assignment_id = (
            current_assignment.id
        )

    if (
        current_assignment is not None
        and current_assignment.id != new_assignment.id
    ):
        current_assignment.is_active = False

    new_assignment.is_active = True

    sync_trip_with_assignment(
        db,
        trip,
        new_assignment,
    )

    db.flush()

    return new_assignment


def restore_previous_assignment(
    db: Session,
    trip: Trip,
):
    """
    آخرین تخصیص جایگزین را پایان می‌دهد و
    تخصیص مشخص‌شده در replaces_assignment_id را
    دوباره فعال می‌کند.

    این تابع برای پایان عملیات جایگزین موقت
    قابل استفاده است.
    """

    current_assignment = get_active_assignment(
        db,
        trip.id,
    )

    if current_assignment is None:
        return None

    current_assignment.is_active = False

    db.flush()

    if current_assignment.replaces_assignment_id is None:

        trip.driver_id = None
        trip.vehicle_id = None

        db.flush()

        return None

    previous_assignment = (
        db.query(TripAssignment)
        .filter(
            TripAssignment.id
            == current_assignment.replaces_assignment_id,
            TripAssignment.trip_id
            == trip.id,
        )
        .first()
    )

    if previous_assignment is None:

        trip.driver_id = None
        trip.vehicle_id = None

        db.flush()

        return None

    previous_assignment.is_active = True

    sync_trip_with_assignment(
        db,
        trip,
        previous_assignment,
    )

    db.flush()

    return previous_assignment