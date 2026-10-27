from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation
from app.models.trip import Trip
from app.models.student import Student
from app.models.user import User

from app.schemas.reservation import (
    ReservationCreate,
    ReservationResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_trip_company_access,
)

from app.core.roles import (
    Roles,
    MANAGEMENT_ROLES,
)

from app.services.reservation_service import (
    create_reservation,
    cancel_reservation,
)


router = APIRouter(
    prefix="/reservations",
    tags=["Reservations"],
)


CREATE_ROLES = MANAGEMENT_ROLES | {
    Roles.STUDENT,
    Roles.COMPANY_ADMIN,
}

VIEW_ROLES = CREATE_ROLES | {
    Roles.DRIVER,
}


def get_trip_or_404(
    db: Session,
    trip_id: int,
) -> Trip:
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    return trip


def get_student_or_404(
    db: Session,
    student_id: int,
) -> Student:
    student = (
        db.query(Student)
        .filter(Student.id == student_id)
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو پیدا نشد",
        )

    return student


def check_trip_access(
    db: Session,
    current_user: User,
    trip: Trip,
) -> None:
    if current_user.role == Roles.COMPANY_ADMIN:
        check_trip_company_access(
            db,
            current_user,
            trip,
        )
        return

    check_university_access(
        current_user=current_user,
        university_id=trip.university_id,
    )


def check_driver_trip_access(
    current_user: User,
    trip: Trip,
) -> None:
    if current_user.role != Roles.DRIVER:
        return

    if current_user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری راننده به یک راننده متصل نیست",
        )

    if trip.driver_id != current_user.driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است",
        )


def check_student_trip_consistency(
    student: Student,
    trip: Trip,
) -> None:
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو و سفر متعلق به یک دانشگاه نیستند",
        )


@router.post(
    "/",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation_endpoint(
    reservation_data: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in CREATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ثبت رزرو ندارید",
        )

    trip = get_trip_or_404(
        db,
        reservation_data.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    student = get_student_or_404(
        db,
        reservation_data.student_id,
    )

    check_student_trip_consistency(
        student,
        trip,
    )

    if current_user.role == Roles.STUDENT:
        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به یک دانشجو متصل نیست",
            )

        if student.id != current_user.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید برای حساب خودتان رزرو ثبت کنید",
            )

    return create_reservation(
        db,
        trip_id=reservation_data.trip_id,
        student_id=reservation_data.student_id,
        is_standing=reservation_data.is_standing,
    )


@router.get(
    "/",
    response_model=list[ReservationResponse],
)
def get_reservations(
    trip_id: int | None = Query(
        default=None,
        description="شناسه سفر",
    ),
    student_id: int | None = Query(
        default=None,
        description="شناسه دانشجو",
    ),
    only_active: bool = Query(
        default=True,
        description="فقط رزروهای فعال",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده رزروها را ندارید",
        )

    if current_user.role == Roles.STUDENT:
        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به یک دانشجو متصل نیست",
            )

        if (
            student_id is not None
            and student_id != current_user.student_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید رزروهای خودتان را مشاهده کنید",
            )

        student_id = current_user.student_id

    trip = None

    if trip_id is not None:
        trip = get_trip_or_404(
            db,
            trip_id,
        )

        check_trip_access(
            db,
            current_user,
            trip,
        )

        check_driver_trip_access(
            current_user,
            trip,
        )

    if current_user.role == Roles.COMPANY_ADMIN and trip_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای مشاهده رزروها توسط شرکت، تعیین سفر الزامی است",
        )

    query = (
        db.query(Reservation)
        .join(
            Trip,
            Trip.id == Reservation.trip_id,
        )
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        query = query.filter(
            Reservation.trip_id == trip_id,
        )

    elif current_user.role != Roles.SUPER_ADMIN:
        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Trip.university_id == current_user.university_id,
        )

    if student_id is not None:
        student = get_student_or_404(
            db,
            student_id,
        )

        if current_user.role == Roles.COMPANY_ADMIN:
            check_student_trip_consistency(
                student,
                trip,
            )

        elif current_user.role != Roles.SUPER_ADMIN:
            check_university_access(
                current_user=current_user,
                university_id=student.university_id,
            )

        query = query.filter(
            Reservation.student_id == student_id,
        )

    if trip_id is not None:
        query = query.filter(
            Reservation.trip_id == trip_id,
        )

    if only_active:
        query = query.filter(
            Reservation.status == "active",
        )

    return (
        query
        .order_by(
            Reservation.reservation_time.desc(),
        )
        .all()
    )


@router.get(
    "/{reservation_id}",
    response_model=ReservationResponse,
)
def get_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده رزروها را ندارید",
        )

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رزرو موردنظر پیدا نشد",
        )

    trip = get_trip_or_404(
        db,
        reservation.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    if current_user.role == Roles.STUDENT:
        if current_user.student_id != reservation.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما به این رزرو دسترسی ندارید",
            )

    return reservation


@router.patch(
    "/{reservation_id}/cancel",
    response_model=ReservationResponse,
)
def cancel_reservation_endpoint(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in CREATE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز لغو رزرو ندارید",
        )

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.id == reservation_id,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رزرو موردنظر پیدا نشد",
        )

    trip = get_trip_or_404(
        db,
        reservation.trip_id,
    )

    check_trip_access(
        db,
        current_user,
        trip,
    )

    check_driver_trip_access(
        current_user,
        trip,
    )

    if current_user.role == Roles.STUDENT:
        if current_user.student_id != reservation.student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید رزرو خودتان را لغو کنید",
            )

    return cancel_reservation(
        db,
        reservation_id=reservation_id,
    )