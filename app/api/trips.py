from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.trip import Trip
from app.models.user import User
from app.models.service import Service
from app.models.schedule import Schedule
from app.models.contract import Contract

from app.schemas.trip import (
    TripCreate,
    TripResponse,
    TripStatusUpdate,
    TripFromScheduleCreate,
    DailyTripGenerationRequest,
    TripAssignmentUpdate,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_company_user,
    check_driver_contract_access,
    check_vehicle_contract_access,
    check_trip_company_access,
)

from app.core.roles import (
    Roles,
    TRIP_VIEW_ROLES,
    TRIP_MANAGEMENT_ROLES,
)

from app.services.trip_service import (
    TRIP_STATUSES,
    create_trip,
    create_trip_from_schedule,
    generate_daily_trips,
    assign_trip_resources,
    update_trip_status,
)

from app.services.eta_service import get_next_station


router = APIRouter(
    prefix="/trips",
    tags=["Trips"],
)


# =========================================================
# Internal Helpers
# =========================================================

def _validate_positive_id(
    value: int,
    field_name: str,
) -> None:
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} باید عددی مثبت باشد",
        )


def _get_trip(
    db: Session,
    trip_id: int,
) -> Trip:

    _validate_positive_id(
        trip_id,
        "شناسه سفر",
    )

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


def _get_service(
    db: Session,
    service_id: int,
) -> Service:

    _validate_positive_id(
        service_id,
        "شناسه سرویس",
    )

    service = (
        db.query(Service)
        .filter(Service.id == service_id)
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس موردنظر پیدا نشد",
        )

    return service


def _get_schedule(
    db: Session,
    schedule_id: int,
) -> Schedule:

    _validate_positive_id(
        schedule_id,
        "شناسه برنامه زمانی",
    )

    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id)
        .first()
    )

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برنامه زمانی موردنظر پیدا نشد",
        )

    return schedule


def _check_company_service_access(
    db: Session,
    current_user: User,
    service: Service,
    university_id: int,
) -> Contract:

    check_company_user(current_user)

    _validate_positive_id(
        university_id,
        "شناسه دانشگاه",
    )

    if service.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه سرویس با دانشگاه سفر مطابقت ندارد",
        )

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="سرویس غیرفعال است",
        )

    if service.contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس تحت قرارداد شرکت حمل‌ونقل قرار ندارد",
        )

    contract = service.contract

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="قرارداد سرویس پیدا نشد",
        )

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="قرارداد سرویس غیرفعال است",
        )

    if (
        contract.transport_company_id
        != current_user.transport_company_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس تحت قرارداد شرکت شما نیست",
        )

    if contract.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه قرارداد با دانشگاه سرویس مطابقت ندارد",
        )

    return contract


def _check_company_schedule_access(
    db: Session,
    current_user: User,
    schedule_id: int,
    university_id: int,
):
    schedule = _get_schedule(
        db=db,
        schedule_id=schedule_id,
    )

    if schedule.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه برنامه زمانی با دانشگاه سفر مطابقت ندارد",
        )

    if not schedule.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="برنامه زمانی غیرفعال است",
        )

    service = schedule.service

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="سرویس برنامه زمانی پیدا نشد",
        )

    contract = _check_company_service_access(
        db=db,
        current_user=current_user,
        service=service,
        university_id=university_id,
    )

    return schedule, service, contract


def _check_company_trip_resources(
    db: Session,
    current_user: User,
    contract: Contract,
    driver_id: int | None,
    vehicle_id: int | None,
) -> None:

    if driver_id is not None:

        _validate_positive_id(
            driver_id,
            "شناسه راننده",
        )

        check_driver_contract_access(
            db=db,
            current_user=current_user,
            contract_id=contract.id,
            driver_id=driver_id,
        )

    if vehicle_id is not None:

        _validate_positive_id(
            vehicle_id,
            "شناسه خودرو",
        )

        check_vehicle_contract_access(
            db=db,
            current_user=current_user,
            contract_id=contract.id,
            vehicle_id=vehicle_id,
        )


def _check_driver_trip_access(
    trip: Trip,
    current_user: User,
) -> None:

    if current_user.role != Roles.DRIVER:
        return

    if current_user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب راننده به راننده‌ای متصل نیست",
        )

    if trip.driver_id != current_user.driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما فقط به سفرهای خود دسترسی دارید",
        )


def _check_trip_university_access(
    current_user: User,
    trip: Trip,
) -> None:

    check_university_access(
        current_user=current_user,
        university_id=trip.university_id,
    )


# =========================================================
# Create Trip - Manual
# =========================================================

@router.post(
    "/",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_endpoint(
    trip_data: TripCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد سفر را ندارید",
        )

    _validate_positive_id(
        trip_data.university_id,
        "شناسه دانشگاه",
    )

    service = _get_service(
        db=db,
        service_id=trip_data.service_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        contract = _check_company_service_access(
            db=db,
            current_user=current_user,
            service=service,
            university_id=trip_data.university_id,
        )

        _check_company_trip_resources(
            db=db,
            current_user=current_user,
            contract=contract,
            driver_id=trip_data.driver_id,
            vehicle_id=trip_data.vehicle_id,
        )

    else:

        check_university_access(
            current_user=current_user,
            university_id=trip_data.university_id,
        )

    trip = create_trip(
        db=db,
        university_id=trip_data.university_id,
        service_id=trip_data.service_id,
        schedule_id=trip_data.schedule_id,
        driver_id=trip_data.driver_id,
        vehicle_id=trip_data.vehicle_id,
        seated_capacity=trip_data.seated_capacity,
        standing_capacity=trip_data.standing_capacity,
        allow_standing=trip_data.allow_standing,
        trip_date=trip_data.trip_date,
        planned_departure_time=trip_data.planned_departure_time,
        trip_status=trip_data.status,
        is_active=trip_data.is_active,
    )

    return trip


# =========================================================
# Create Trip From Schedule
# =========================================================

@router.post(
    "/from-schedule",
    response_model=TripResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trip_from_schedule_endpoint(
    trip_data: TripFromScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد سفر را ندارید",
        )

    _validate_positive_id(
        trip_data.university_id,
        "شناسه دانشگاه",
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        _, _, contract = _check_company_schedule_access(
            db=db,
            current_user=current_user,
            schedule_id=trip_data.schedule_id,
            university_id=trip_data.university_id,
        )

        _check_company_trip_resources(
            db=db,
            current_user=current_user,
            contract=contract,
            driver_id=trip_data.driver_id,
            vehicle_id=trip_data.vehicle_id,
        )

    else:

        check_university_access(
            current_user=current_user,
            university_id=trip_data.university_id,
        )

    trip = create_trip_from_schedule(
        db=db,
        university_id=trip_data.university_id,
        schedule_id=trip_data.schedule_id,
        trip_date=trip_data.trip_date,
        driver_id=trip_data.driver_id,
        vehicle_id=trip_data.vehicle_id,
        seated_capacity=trip_data.seated_capacity,
        standing_capacity=trip_data.standing_capacity,
        allow_standing=trip_data.allow_standing,
        is_active=trip_data.is_active,
    )

    return trip


# =========================================================
# Generate Daily Trips
# =========================================================

@router.post(
    "/generate-daily",
    response_model=list[TripResponse],
    status_code=status.HTTP_201_CREATED,
)
def generate_daily_trips_endpoint(
    request_data: DailyTripGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تولید سفرهای روزانه را ندارید",
        )

    _validate_positive_id(
        request_data.university_id,
        "شناسه دانشگاه",
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تولید گروهی سفر برای شرکت حمل‌ونقل هنوز به‌صورت قراردادی محدود نشده است",
        )

    check_university_access(
        current_user=current_user,
        university_id=request_data.university_id,
    )

    return generate_daily_trips(
        db=db,
        university_id=request_data.university_id,
        trip_date=request_data.trip_date,
    )


# =========================================================
# Assign Driver / Vehicle
# =========================================================

@router.patch(
    "/{trip_id}/assignment",
    response_model=TripResponse,
)
def assign_trip_resources_endpoint(
    trip_id: int,
    assignment_data: TripAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تخصیص راننده یا خودرو را ندارید",
        )

    trip = _get_trip(
        db=db,
        trip_id=trip_id,
    )

    if (
        assignment_data.driver_id is None
        and assignment_data.vehicle_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل راننده یا خودرو باید مشخص شود",
        )

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db=db,
            current_user=current_user,
            trip_id=trip_id,
        )

        service = trip.service

        if service is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="سرویس سفر پیدا نشد",
            )

        if service.contract_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="سفر تحت قرارداد شرکت قرار ندارد",
            )

        contract = service.contract

        if contract is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="قرارداد سفر پیدا نشد",
            )

        if not contract.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="قرارداد سفر غیرفعال است",
            )

        if (
            contract.transport_company_id
            != current_user.transport_company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="قرارداد سفر متعلق به شرکت شما نیست",
            )

        _check_company_trip_resources(
            db=db,
            current_user=current_user,
            contract=contract,
            driver_id=assignment_data.driver_id,
            vehicle_id=assignment_data.vehicle_id,
        )

    else:

        _check_trip_university_access(
            current_user=current_user,
            trip=trip,
        )

    return assign_trip_resources(
        db=db,
        trip=trip,
        driver_id=assignment_data.driver_id,
        vehicle_id=assignment_data.vehicle_id,
    )


# =========================================================
# Get Trips
# =========================================================

@router.get(
    "/",
    response_model=list[TripResponse],
)
def get_trips(
    trip_date: date | None = Query(
        default=None,
        description="تاریخ سفر",
    ),
    service_id: int | None = Query(
        default=None,
        description="شناسه سرویس",
    ),
    driver_id: int | None = Query(
        default=None,
        description="شناسه راننده",
    ),
    trip_status: str | None = Query(
        default=None,
        alias="status",
        description="وضعیت سفر",
    ),
    university_id: int | None = Query(
        default=None,
        description="شناسه دانشگاه",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده سفرها را ندارید",
        )

    if service_id is not None:
        _validate_positive_id(
            service_id,
            "شناسه سرویس",
        )

    if driver_id is not None:
        _validate_positive_id(
            driver_id,
            "شناسه راننده",
        )

    if university_id is not None:
        _validate_positive_id(
            university_id,
            "شناسه دانشگاه",
        )

    query = db.query(Trip)

    # -----------------------------------------------------
    # Super Admin
    # -----------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:

        if university_id is not None:
            query = query.filter(
                Trip.university_id == university_id
            )

    # -----------------------------------------------------
    # Company Admin
    # -----------------------------------------------------

    elif current_user.role == Roles.COMPANY_ADMIN:

        check_company_user(current_user)

        query = (
            query
            .join(
                Service,
                Service.id == Trip.service_id,
            )
            .join(
                Contract,
                Contract.id == Service.contract_id,
            )
            .filter(
                Service.contract_id.isnot(None),
                Service.is_active.is_(True),
                Contract.is_active.is_(True),
                Contract.transport_company_id
                == current_user.transport_company_id,
                Contract.university_id
                == Trip.university_id,
                Service.university_id
                == Trip.university_id,
            )
        )

        if university_id is not None:
            query = query.filter(
                Trip.university_id == university_id
            )

    # -----------------------------------------------------
    # University / Other Users
    # -----------------------------------------------------

    else:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        if university_id is not None:
            if university_id != current_user.university_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="شما به این دانشگاه دسترسی ندارید",
                )

        query = query.filter(
            Trip.university_id
            == current_user.university_id
        )

    # -----------------------------------------------------
    # Service Filter
    # -----------------------------------------------------

    if service_id is not None:
        query = query.filter(
            Trip.service_id == service_id
        )

    # -----------------------------------------------------
    # Driver Restriction
    # -----------------------------------------------------

    if current_user.role == Roles.DRIVER:

        if current_user.driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب راننده به راننده‌ای متصل نیست",
            )

        query = query.filter(
            Trip.driver_id == current_user.driver_id
        )

    elif driver_id is not None:

        query = query.filter(
            Trip.driver_id == driver_id
        )

    # -----------------------------------------------------
    # Date Filter
    # -----------------------------------------------------

    if trip_date is not None:
        query = query.filter(
            Trip.trip_date == trip_date
        )

    # -----------------------------------------------------
    # Status Filter
    # -----------------------------------------------------

    if trip_status is not None:

        trip_status = (
            trip_status.strip().lower()
        )

        if trip_status not in TRIP_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="وضعیت سفر نامعتبر است",
            )

        query = query.filter(
            Trip.status == trip_status
        )

    return (
        query
        .order_by(
            Trip.trip_date.asc(),
            Trip.planned_departure_time.asc(),
        )
        .all()
    )


# =========================================================
# Get Trip By ID
# =========================================================

@router.get(
    "/{trip_id}",
    response_model=TripResponse,
)
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    trip = _get_trip(
        db=db,
        trip_id=trip_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db=db,
            current_user=current_user,
            trip_id=trip_id,
        )

    else:

        _check_trip_university_access(
            current_user=current_user,
            trip=trip,
        )

    _check_driver_trip_access(
        trip=trip,
        current_user=current_user,
    )

    return trip


# =========================================================
# Update Trip Status
# =========================================================

@router.patch(
    "/{trip_id}/status",
    response_model=TripResponse,
)
def update_trip_status_endpoint(
    trip_id: int,
    status_data: TripStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in TRIP_MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت سفر را ندارید",
        )

    trip = _get_trip(
        db=db,
        trip_id=trip_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db=db,
            current_user=current_user,
            trip_id=trip_id,
        )

    else:

        _check_trip_university_access(
            current_user=current_user,
            trip=trip,
        )

    return update_trip_status(
        db=db,
        trip=trip,
        new_status=status_data.status,
    )


# =========================================================
# ETA - Next Station
# =========================================================

@router.get(
    "/{trip_id}/eta/next-station",
)
def get_trip_next_station(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    trip = _get_trip(
        db=db,
        trip_id=trip_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db=db,
            current_user=current_user,
            trip_id=trip_id,
        )

    else:

        _check_trip_university_access(
            current_user=current_user,
            trip=trip,
        )

    _check_driver_trip_access(
        trip=trip,
        current_user=current_user,
    )

    return get_next_station(
        db=db,
        trip_id=trip_id,
    )
