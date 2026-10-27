from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.trip_passenger import TripPassenger
from app.models.trip import Trip
from app.models.user import User
from app.models.student import Student

from app.schemas.trip_passenger import (
    TripPassengerCreate,
    TripPassengerBoardRequest,
    TripPassengerResponse,
    TripPassengerQRBoardRequest,
)

from app.services.student_qr_service import get_student_by_qr_token

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_trip_company_access,
)

from app.core.roles import (
    Roles,
    TRIP_VIEW_ROLES,
    TRIP_MANAGEMENT_ROLES,
)

from app.services.trip_passenger_service import (
    create_trip_passenger,
    board_passenger,
    alight_passenger,
)


router = APIRouter(
    prefix="/trip-passengers",
    tags=["Trip Passengers"],
)


# =========================================================
# Helpers
# =========================================================

def validate_positive_id(
    value: int,
    field_name: str,
) -> None:

    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} باید بزرگ‌تر از صفر باشد",
        )


def get_passenger_or_404(
    db: Session,
    passenger_id: int,
) -> TripPassenger:

    validate_positive_id(
        passenger_id,
        "شناسه مسافر",
    )

    passenger = (
        db.query(TripPassenger)
        .filter(
            TripPassenger.id == passenger_id
        )
        .first()
    )

    if passenger is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رکورد مسافر پیدا نشد",
        )

    return passenger


def get_trip_or_404(
    db: Session,
    trip_id: int,
) -> Trip:

    validate_positive_id(
        trip_id,
        "شناسه سفر",
    )

    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id
        )
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

    validate_positive_id(
        student_id,
        "شناسه دانشجو",
    )

    student = (
        db.query(Student)
        .filter(
            Student.id == student_id
        )
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
            detail="حساب راننده به یک راننده متصل نیست",
        )

    if trip.driver_id != current_user.driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است",
        )


def check_student_passenger_access(
    current_user: User,
    passenger: TripPassenger,
) -> None:

    if current_user.role != Roles.STUDENT:
        return

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب دانشجو به یک دانشجو متصل نیست",
        )

    if passenger.student_id != current_user.student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما فقط به اطلاعات سفرهای خودتان دسترسی دارید",
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


def check_passenger_management_access(
    current_user: User,
) -> None:

    if (
        current_user.role not in TRIP_MANAGEMENT_ROLES
        and current_user.role not in {
            Roles.COMPANY_ADMIN,
            Roles.DRIVER,
        }
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت مسافران سفر را ندارید",
        )


# =========================================================
# Create Passenger
# Management / Company / Driver
# =========================================================

@router.post(
    "/",
    response_model=TripPassengerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_passenger_endpoint(
    passenger_data: TripPassengerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_passenger_management_access(
        current_user,
    )

    trip = get_trip_or_404(
        db,
        passenger_data.trip_id,
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
        passenger_data.student_id,
    )

    check_student_trip_consistency(
        student,
        trip,
    )

    passenger = create_trip_passenger(
        db=db,
        trip_id=passenger_data.trip_id,
        student_id=passenger_data.student_id,
        boarding_method=passenger_data.boarding_method,
        is_standing=passenger_data.is_standing,
        boarding_station_id=passenger_data.boarding_station_id,
        alighting_station_id=passenger_data.alighting_station_id,
    )

    return passenger


# =========================================================
# Board Passenger
# =========================================================

@router.post(
    "/{trip_id}/board",
    response_model=TripPassengerResponse,
    status_code=status.HTTP_201_CREATED,
)
def board_passenger_endpoint(
    trip_id: int,
    passenger_data: TripPassengerBoardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_passenger_management_access(
        current_user,
    )

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

    student = get_student_or_404(
        db,
        passenger_data.student_id,
    )

    check_student_trip_consistency(
        student,
        trip,
    )

    passenger = board_passenger(
        db=db,
        trip_id=trip_id,
        student_id=passenger_data.student_id,
        boarding_method=passenger_data.boarding_method,
        is_standing=passenger_data.is_standing,
        boarding_station_id=passenger_data.boarding_station_id,
    )

    return passenger


# =========================================================
# Board Passenger By QR
# Management / Company / Driver
# =========================================================

@router.post(
    "/{trip_id}/board/qr",
    response_model=TripPassengerResponse,
    status_code=status.HTTP_201_CREATED,
)
def board_passenger_by_qr(
    trip_id: int,
    passenger_data: TripPassengerQRBoardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_passenger_management_access(
        current_user,
    )

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

    student = get_student_by_qr_token(
        db=db,
        qr_token=passenger_data.qr_token,
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو با این QR Code پیدا نشد",
        )

    check_student_trip_consistency(
        student,
        trip,
    )

    passenger = board_passenger(
        db=db,
        trip_id=trip_id,
        student_id=student.id,
        boarding_method="qr",
        is_standing=passenger_data.is_standing,
        boarding_station_id=passenger_data.boarding_station_id,
    )

    return passenger


# =========================================================
# Get Trip Passengers
# =========================================================

@router.get(
    "/",
    response_model=list[TripPassengerResponse],
)
def get_trip_passengers(
    trip_id: int | None = Query(
        default=None,
        description="شناسه سفر",
    ),
    student_id: int | None = Query(
        default=None,
        description="شناسه دانشجو",
    ),
    only_onboard: bool = Query(
        default=False,
        description="فقط مسافران حاضر در سفر",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده مسافران سفر را ندارید",
        )

    if trip_id is not None:
        validate_positive_id(
            trip_id,
            "شناسه سفر",
        )

    if student_id is not None:
        validate_positive_id(
            student_id,
            "شناسه دانشجو",
        )

    # -----------------------------------------------------
    # Student restriction
    # -----------------------------------------------------

    if current_user.role == Roles.STUDENT:

        if current_user.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب دانشجو به یک دانشجو متصل نیست",
            )

        if (
            student_id is not None
            and student_id != current_user.student_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید اطلاعات سفرهای خودتان را مشاهده کنید",
            )

        student_id = current_user.student_id

    # -----------------------------------------------------
    # Specific trip access
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Company access
    # -----------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        if trip_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای مشاهده مسافران توسط شرکت، تعیین سفر الزامی است",
            )

    # -----------------------------------------------------
    # Base query
    # -----------------------------------------------------

    query = (
        db.query(TripPassenger)
        .join(
            Trip,
            Trip.id == TripPassenger.trip_id,
        )
    )

    # -----------------------------------------------------
    # University / company isolation
    # -----------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        query = query.filter(
            TripPassenger.trip_id == trip_id
        )

    elif current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Trip.university_id == current_user.university_id
        )

    # -----------------------------------------------------
    # Student filter
    # -----------------------------------------------------

    if student_id is not None:

        student = get_student_or_404(
            db,
            student_id,
        )

        if current_user.role == Roles.COMPANY_ADMIN:

            if trip is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="برای جست‌وجوی دانشجو توسط شرکت، تعیین سفر الزامی است",
                )

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
            TripPassenger.student_id == student_id
        )

    # -----------------------------------------------------
    # Trip filter
    # -----------------------------------------------------

    if trip_id is not None:

        query = query.filter(
            TripPassenger.trip_id == trip_id
        )

    # -----------------------------------------------------
    # Only onboard
    # -----------------------------------------------------

    if only_onboard:

        query = query.filter(
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
        )

    # -----------------------------------------------------
    # Driver restriction
    # -----------------------------------------------------

    if current_user.role == Roles.DRIVER:

        if current_user.driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب راننده به یک راننده متصل نیست",
            )

        query = query.filter(
            Trip.driver_id == current_user.driver_id
        )

    return (
        query
        .order_by(
            TripPassenger.boarding_time.asc()
        )
        .all()
    )


# =========================================================
# Get Passenger By ID
# =========================================================

@router.get(
    "/{passenger_id}",
    response_model=TripPassengerResponse,
)
def get_trip_passenger(
    passenger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این مسافر را ندارید",
        )

    passenger = get_passenger_or_404(
        db,
        passenger_id,
    )

    trip = get_trip_or_404(
        db,
        passenger.trip_id,
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

    check_student_passenger_access(
        current_user,
        passenger,
    )

    return passenger


# =========================================================
# Alight Passenger
# =========================================================

@router.patch(
    "/{passenger_id}/alight",
    response_model=TripPassengerResponse,
)
def alight_trip_passenger_endpoint(
    passenger_id: int,
    alighting_station_id: int | None = Query(
        default=None,
        description="شناسه ایستگاه پیاده‌شدن",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_passenger_management_access(
        current_user,
    )

    if alighting_station_id is not None:
        validate_positive_id(
            alighting_station_id,
            "شناسه ایستگاه پیاده‌شدن",
        )

    passenger = get_passenger_or_404(
        db,
        passenger_id,
    )

    trip = get_trip_or_404(
        db,
        passenger.trip_id,
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

    passenger = alight_passenger(
        db=db,
        passenger_id=passenger_id,
        alighting_station_id=alighting_station_id,
    )

    return passenger