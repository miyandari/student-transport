from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.trip import Trip
from app.models.service import Service
from app.models.schedule import Schedule
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.models.university import University
from app.models.contract import Contract
from app.models.contract_driver import ContractDriver
from app.models.contract_vehicle import ContractVehicle
from app.services.trip_lifecycle_service import process_trip_no_shows


TRIP_STATUSES = {
    "scheduled",
    "boarding",
    "in_progress",
    "completed",
    "cancelled",
}


VALID_TRANSITIONS = {
    "scheduled": {
        "boarding",
        "cancelled",
    },
    "boarding": {
        "in_progress",
        "cancelled",
    },
    "in_progress": {
        "completed",
    },
    "completed": set(),
    "cancelled": set(),
}


# ایران از سال ۱۴۰۱ تغییر ساعت تابستانی ندارد.
# بنابراین برای این پروژه از Offset ثابت +03:30 استفاده می‌کنیم
# تا وابستگی به tzdata / ZoneInfo ایجاد نشود.
IRAN_TZ = timezone(timedelta(hours=3, minutes=30))


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
            detail=f"{field_name} باید عددی مثبت باشد",
        )


def normalize_utc_datetime(
    value: datetime,
) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان باید دارای منطقه زمانی باشد",
        )

    return value.astimezone(timezone.utc)


def to_iran_datetime(
    value: datetime,
) -> datetime:
    """
    تبدیل زمان آگاه از منطقه زمانی به زمان ایران +03:30.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان باید دارای منطقه زمانی باشد",
        )

    return value.astimezone(IRAN_TZ)


def iran_datetime_to_utc(
    trip_date: date,
    local_time,
) -> datetime:
    """
    ساخت زمان UTC از تاریخ و ساعت محلی ایران.
    """
    local_datetime = datetime.combine(
        trip_date,
        local_time,
    ).replace(
        tzinfo=IRAN_TZ
    )

    return local_datetime.astimezone(timezone.utc)


def get_system_day_of_week(
    value: date,
) -> int:
    """
    قرارداد روزهای هفته در سیستم:

    شنبه = 0
    یکشنبه = 1
    دوشنبه = 2
    سه‌شنبه = 3
    چهارشنبه = 4
    پنج‌شنبه = 5
    جمعه = 6
    """

    return (value.weekday() + 2) % 7


def get_university(
    db: Session,
    university_id: int,
) -> University:

    validate_positive_id(
        university_id,
        "شناسه دانشگاه",
    )

    university = (
        db.query(University)
        .filter(
            University.id == university_id
        )
        .first()
    )

    if university is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشگاه موردنظر پیدا نشد",
        )

    if not university.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه غیرفعال است",
        )

    return university


def get_service(
    db: Session,
    service_id: int,
    university_id: int,
) -> Service:

    validate_positive_id(
        service_id,
        "شناسه سرویس",
    )

    service = (
        db.query(Service)
        .filter(
            Service.id == service_id
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس موردنظر پیدا نشد",
        )

    if service.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="سرویس متعلق به این دانشگاه نیست",
        )

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس غیرفعال است",
        )

    return service


def get_schedule(
    db: Session,
    schedule_id: int,
    university_id: int,
    service_id: int | None = None,
) -> Schedule:

    validate_positive_id(
        schedule_id,
        "شناسه برنامه زمانی",
    )

    schedule = (
        db.query(Schedule)
        .filter(
            Schedule.id == schedule_id
        )
        .first()
    )

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برنامه زمانی موردنظر پیدا نشد",
        )

    if schedule.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="برنامه زمانی متعلق به این دانشگاه نیست",
        )

    if (
        service_id is not None
        and schedule.service_id != service_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برنامه زمانی متعلق به این سرویس نیست",
        )

    if not schedule.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برنامه زمانی غیرفعال است",
        )

    return schedule


def get_driver(
    db: Session,
    driver_id: int,
    university_id: int,
) -> Driver:

    validate_positive_id(
        driver_id,
        "شناسه راننده",
    )

    driver = (
        db.query(Driver)
        .filter(
            Driver.id == driver_id
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده موردنظر پیدا نشد",
        )

    if driver.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="راننده متعلق به این دانشگاه نیست",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده غیرفعال است",
        )

    return driver


def get_vehicle(
    db: Session,
    vehicle_id: int,
    university_id: int,
) -> Vehicle:

    validate_positive_id(
        vehicle_id,
        "شناسه خودرو",
    )

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو موردنظر پیدا نشد",
        )

    if vehicle.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="خودرو متعلق به این دانشگاه نیست",
        )

    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو غیرفعال است",
        )

    return vehicle


def get_trip_time_interval(
    trip: Trip,
) -> tuple[datetime, datetime | None]:
    """
    بازه زمانی سفر را بر اساس زمان حرکت و برنامه زمانی
    محاسبه می‌کند.
    """

    trip_start = normalize_utc_datetime(
        trip.planned_departure_time
    )

    schedule = trip.schedule

    if (
        schedule is None
        or schedule.arrival_time is None
    ):
        return trip_start, None

    trip_end = iran_datetime_to_utc(
        trip.trip_date,
        schedule.arrival_time,
    )

    if trip_end <= trip_start:
        return trip_start, None

    return trip_start, trip_end


# =========================================================
# Contract Validation
# =========================================================

def get_service_contract(
    db: Session,
    service: Service,
) -> Contract | None:

    if service.contract_id is None:
        return None

    contract = (
        db.query(Contract)
        .filter(
            Contract.id == service.contract_id
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد سرویس پیدا نشد",
        )

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد سرویس غیرفعال است",
        )

    if contract.university_id != service.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="قرارداد سرویس متعلق به دانشگاه سرویس نیست",
        )

    return contract


def validate_trip_contract_date(
    trip_date: date,
    contract: Contract | None,
) -> None:

    if contract is None:
        return

    if trip_date < contract.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ سفر قبل از شروع قرارداد است",
        )

    if trip_date > contract.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ سفر بعد از پایان قرارداد است",
        )


def validate_driver_contract_assignment(
    db: Session,
    driver: Driver,
    contract: Contract | None,
    trip_date: date,
) -> None:

    if contract is None:
        return

    assignment = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == contract.id,
            ContractDriver.driver_id == driver.id,
            ContractDriver.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده به قرارداد این سفر تخصیص داده نشده است",
        )

    if (
        assignment.start_date is not None
        and trip_date < assignment.start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده در تاریخ سفر هنوز در قرارداد فعال نشده است",
        )

    if (
        assignment.end_date is not None
        and trip_date > assignment.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اعتبار تخصیص راننده در تاریخ سفر به پایان رسیده است",
        )


def validate_vehicle_contract_assignment(
    db: Session,
    vehicle: Vehicle,
    contract: Contract | None,
    trip_date: date,
) -> None:

    if contract is None:
        return

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == contract.id,
            ContractVehicle.vehicle_id == vehicle.id,
            ContractVehicle.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو به قرارداد این سفر تخصیص داده نشده است",
        )

    if (
        assignment.start_date is not None
        and trip_date < assignment.start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودرو در تاریخ سفر هنوز در قرارداد فعال نشده است",
        )

    if (
        assignment.end_date is not None
        and trip_date > assignment.end_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اعتبار تخصیص خودرو در تاریخ سفر به پایان رسیده است",
        )


# =========================================================
# Validation
# =========================================================

def validate_driver_vehicle(
    driver: Driver | None,
    vehicle: Vehicle | None,
) -> None:

    if (
        driver is not None
        and vehicle is not None
        and vehicle.driver_id is not None
        and vehicle.driver_id != driver.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده انتخاب‌شده با راننده اختصاص‌یافته به خودرو مطابقت ندارد",
        )


def validate_capacity(
    seated_capacity: int | None,
    standing_capacity: int | None,
    allow_standing: bool,
) -> None:

    if (
        seated_capacity is not None
        and seated_capacity <= 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ظرفیت صندلی باید بیشتر از صفر باشد",
        )

    if (
        standing_capacity is not None
        and standing_capacity < 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ظرفیت ایستاده نمی‌تواند منفی باشد",
        )

    if allow_standing:
        if (
            standing_capacity is None
            or standing_capacity <= 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="در صورت مجاز بودن ایستادن، ظرفیت ایستاده باید بیشتر از صفر باشد",
            )
    elif standing_capacity not in (None, 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وقتی ایستادن مجاز نیست، ظرفیت ایستاده باید صفر یا خالی باشد",
        )


def validate_new_trip_status(
    status_value: str,
) -> str:

    status_value = status_value.strip().lower()

    if status_value != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سفر جدید فقط باید با وضعیت scheduled ایجاد شود",
        )

    return status_value


def validate_trip_date_and_time(
    trip_date: date,
    planned_departure_time: datetime,
) -> datetime:

    local_departure_time = to_iran_datetime(
        planned_departure_time
    )

    if local_departure_time.date() != trip_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ زمان حرکت با تاریخ سفر مطابقت ندارد",
        )

    return local_departure_time.astimezone(
        timezone.utc
    )


def validate_schedule_for_trip_date(
    schedule: Schedule,
    trip_date: date,
) -> None:

    expected_day = get_system_day_of_week(
        trip_date
    )

    if schedule.day_of_week != expected_day:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ انتخاب‌شده با روز هفته برنامه زمانی مطابقت ندارد",
        )


def validate_schedule_departure_time(
    schedule: Schedule,
    planned_departure_time: datetime,
) -> None:

    local_departure_time = to_iran_datetime(
        planned_departure_time
    )

    actual_time = local_departure_time.time().replace(
        second=0,
        microsecond=0,
        tzinfo=None,
    )

    expected_time = schedule.departure_time.replace(
        second=0,
        microsecond=0,
    )

    if actual_time != expected_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان حرکت سفر با زمان حرکت برنامه زمانی مطابقت ندارد",
        )


# =========================================================
# Duplicate checks
# =========================================================

def check_duplicate_trip(
    db: Session,
    service_id: int,
    trip_date: date,
    planned_departure_time: datetime,
    trip_id: int | None = None,
) -> None:

    planned_departure_time = normalize_utc_datetime(
        planned_departure_time
    )

    query = (
        db.query(Trip)
        .filter(
            Trip.service_id == service_id,
            Trip.trip_date == trip_date,
            Trip.planned_departure_time
            == planned_departure_time,
            Trip.is_active.is_(True),
        )
    )

    if trip_id is not None:
        validate_positive_id(
            trip_id,
            "شناسه سفر",
        )

        query = query.filter(
            Trip.id != trip_id
        )

    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سرویس در تاریخ و ساعت انتخاب‌شده، سفر فعال دیگری وجود دارد",
        )


def get_existing_schedule_trip(
    db: Session,
    schedule_id: int,
    trip_date: date,
) -> Trip | None:

    validate_positive_id(
        schedule_id,
        "شناسه برنامه زمانی",
    )

    return (
        db.query(Trip)
        .filter(
            Trip.schedule_id == schedule_id,
            Trip.trip_date == trip_date,
            Trip.is_active.is_(True),
        )
        .first()
    )


def check_duplicate_schedule_trip(
    db: Session,
    schedule_id: int,
    trip_date: date,
) -> None:

    existing_trip = get_existing_schedule_trip(
        db=db,
        schedule_id=schedule_id,
        trip_date=trip_date,
    )

    if existing_trip is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این برنامه زمانی در تاریخ انتخاب‌شده، سفر قبلاً ایجاد شده است",
        )


# =========================================================
# Resource Conflict
# =========================================================

def intervals_overlap(
    start_a: datetime,
    end_a: datetime | None,
    start_b: datetime,
    end_b: datetime | None,
) -> bool:

    start_a = normalize_utc_datetime(start_a)
    start_b = normalize_utc_datetime(start_b)

    if end_a is not None:
        end_a = normalize_utc_datetime(end_a)

    if end_b is not None:
        end_b = normalize_utc_datetime(end_b)

    if (
        end_a is not None
        and end_b is not None
    ):
        return (
            start_a < end_b
            and start_b < end_a
        )

    if (
        end_a is None
        and end_b is None
    ):
        return start_a == start_b

    if end_a is None:
        return (
            start_b <= start_a < end_b
        )

    return (
        start_a <= start_b < end_a
    )


def check_resource_conflict(
    db: Session,
    trip: Trip,
    resource_field,
    resource_id: int,
    resource_name: str,
) -> None:

    query = (
        db.query(Trip)
        .filter(
            Trip.id != trip.id,
            resource_field == resource_id,
            Trip.university_id == trip.university_id,
            Trip.trip_date == trip.trip_date,
            Trip.is_active.is_(True),
            Trip.status.notin_(
                ["completed", "cancelled"]
            ),
        )
    )

    trip_start, trip_end = get_trip_time_interval(
        trip
    )

    existing_trips = query.all()

    for existing_trip in existing_trips:

        existing_start, existing_end = (
            get_trip_time_interval(existing_trip)
        )

        if intervals_overlap(
            start_a=trip_start,
            end_a=trip_end,
            start_b=existing_start,
            end_b=existing_end,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"{resource_name} در این بازه زمانی "
                    "به سفر دیگری اختصاص یافته است"
                ),
            )


# =========================================================
# Status Management
# =========================================================

def validate_status_transition(
    current_status: str,
    new_status: str,
) -> None:

    current_status = current_status.strip().lower()
    new_status = new_status.strip().lower()

    if current_status not in TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وضعیت فعلی سفر نامعتبر است",
        )

    if new_status not in TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وضعیت جدید سفر نامعتبر است",
        )

    allowed_statuses = VALID_TRANSITIONS[
        current_status
    ]

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"تغییر وضعیت از {current_status} "
                f"به {new_status} مجاز نیست"
            ),
        )


def apply_status_transition(
    trip: Trip,
    new_status: str,
) -> None:

    now = datetime.now(timezone.utc)

    if new_status == "in_progress":
        trip.actual_departure_time = now

    elif new_status == "completed":

        if trip.actual_departure_time is None:
            trip.actual_departure_time = now

        trip.actual_arrival_time = now

    elif new_status == "cancelled":
        trip.actual_arrival_time = None

    trip.status = new_status


# =========================================================
# Create Trip
# =========================================================

def create_trip(
    db: Session,
    university_id: int,
    service_id: int,
    schedule_id: int | None,
    driver_id: int | None,
    vehicle_id: int | None,
    seated_capacity: int | None,
    standing_capacity: int | None,
    allow_standing: bool,
    trip_date: date,
    planned_departure_time: datetime,
    trip_status: str,
    is_active: bool,
) -> Trip:

    get_university(
        db=db,
        university_id=university_id,
    )

    service = get_service(
        db=db,
        service_id=service_id,
        university_id=university_id,
    )

    contract = get_service_contract(
        db=db,
        service=service,
    )

    validate_trip_contract_date(
        trip_date=trip_date,
        contract=contract,
    )

    schedule = None

    if schedule_id is not None:
        schedule = get_schedule(
            db=db,
            schedule_id=schedule_id,
            university_id=university_id,
            service_id=service.id,
        )

        validate_schedule_for_trip_date(
            schedule=schedule,
            trip_date=trip_date,
        )

    driver = None

    if driver_id is not None:
        driver = get_driver(
            db=db,
            driver_id=driver_id,
            university_id=university_id,
        )

        validate_driver_contract_assignment(
            db=db,
            driver=driver,
            contract=contract,
            trip_date=trip_date,
        )

    vehicle = None

    if vehicle_id is not None:
        vehicle = get_vehicle(
            db=db,
            vehicle_id=vehicle_id,
            university_id=university_id,
        )

        validate_vehicle_contract_assignment(
            db=db,
            vehicle=vehicle,
            contract=contract,
            trip_date=trip_date,
        )

    validate_driver_vehicle(
        driver=driver,
        vehicle=vehicle,
    )

    if seated_capacity is None and vehicle is not None:
        seated_capacity = vehicle.capacity

    validate_capacity(
        seated_capacity=seated_capacity,
        standing_capacity=standing_capacity,
        allow_standing=allow_standing,
    )

    trip_status = validate_new_trip_status(
        trip_status
    )

    planned_departure_time = (
        validate_trip_date_and_time(
            trip_date=trip_date,
            planned_departure_time=planned_departure_time,
        )
    )

    if schedule is not None:
        validate_schedule_departure_time(
            schedule=schedule,
            planned_departure_time=planned_departure_time,
        )

    check_duplicate_trip(
        db=db,
        service_id=service.id,
        trip_date=trip_date,
        planned_departure_time=planned_departure_time,
    )

    trip = Trip(
        university_id=university_id,
        service_id=service.id,
        schedule_id=(
            schedule.id
            if schedule is not None
            else None
        ),
        driver_id=(
            driver.id
            if driver is not None
            else None
        ),
        vehicle_id=(
            vehicle.id
            if vehicle is not None
            else None
        ),
        seated_capacity=seated_capacity,
        standing_capacity=standing_capacity,
        allow_standing=allow_standing,
        trip_date=trip_date,
        planned_departure_time=planned_departure_time,
        status=trip_status,
        is_active=is_active,
    )

    db.add(trip)

    try:
        db.commit()
        db.refresh(trip)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ایجاد سفر به دلیل تکراری بودن یا ناسازگاری اطلاعات انجام نشد",
        )

    return trip


# =========================================================
# Create Trip From Schedule
# =========================================================

def create_trip_from_schedule(
    db: Session,
    university_id: int,
    schedule_id: int,
    trip_date: date,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    seated_capacity: int | None = None,
    standing_capacity: int | None = None,
    allow_standing: bool = False,
    is_active: bool = True,
) -> Trip:

    get_university(
        db=db,
        university_id=university_id,
    )

    schedule = get_schedule(
        db=db,
        schedule_id=schedule_id,
        university_id=university_id,
    )

    validate_schedule_for_trip_date(
        schedule=schedule,
        trip_date=trip_date,
    )

    service = get_service(
        db=db,
        service_id=schedule.service_id,
        university_id=university_id,
    )

    contract = get_service_contract(
        db=db,
        service=service,
    )

    validate_trip_contract_date(
        trip_date=trip_date,
        contract=contract,
    )

    check_duplicate_schedule_trip(
        db=db,
        schedule_id=schedule.id,
        trip_date=trip_date,
    )

    driver = None

    if driver_id is not None:
        driver = get_driver(
            db=db,
            driver_id=driver_id,
            university_id=university_id,
        )

        validate_driver_contract_assignment(
            db=db,
            driver=driver,
            contract=contract,
            trip_date=trip_date,
        )

    vehicle = None

    if vehicle_id is not None:
        vehicle = get_vehicle(
            db=db,
            vehicle_id=vehicle_id,
            university_id=university_id,
        )

        validate_vehicle_contract_assignment(
            db=db,
            vehicle=vehicle,
            contract=contract,
            trip_date=trip_date,
        )

    validate_driver_vehicle(
        driver=driver,
        vehicle=vehicle,
    )

    if seated_capacity is None and vehicle is not None:
        seated_capacity = vehicle.capacity

    validate_capacity(
        seated_capacity=seated_capacity,
        standing_capacity=standing_capacity,
        allow_standing=allow_standing,
    )

    planned_departure_time = iran_datetime_to_utc(
        trip_date,
        schedule.departure_time,
    )

    check_duplicate_trip(
        db=db,
        service_id=service.id,
        trip_date=trip_date,
        planned_departure_time=planned_departure_time,
    )

    trip = Trip(
        university_id=university_id,
        service_id=service.id,
        schedule_id=schedule.id,
        driver_id=(
            driver.id
            if driver is not None
            else None
        ),
        vehicle_id=(
            vehicle.id
            if vehicle is not None
            else None
        ),
        seated_capacity=seated_capacity,
        standing_capacity=standing_capacity,
        allow_standing=allow_standing,
        trip_date=trip_date,
        planned_departure_time=planned_departure_time,
        status="scheduled",
        is_active=is_active,
    )

    db.add(trip)

    try:
        db.commit()
        db.refresh(trip)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ایجاد سفر به دلیل تکراری بودن یا ناسازگاری اطلاعات انجام نشد",
        )

    return trip


# =========================================================
# Generate Daily Trips
# =========================================================

def generate_daily_trips(
    db: Session,
    university_id: int,
    trip_date: date,
) -> list[Trip]:

    get_university(
        db=db,
        university_id=university_id,
    )

    system_day_of_week = (
        get_system_day_of_week(trip_date)
    )

    schedules = (
        db.query(Schedule)
        .join(
            Service,
            Service.id == Schedule.service_id,
        )
        .filter(
            Schedule.university_id == university_id,
            Schedule.day_of_week == system_day_of_week,
            Schedule.is_active.is_(True),
            Service.is_active.is_(True),
        )
        .order_by(
            Schedule.departure_time.asc()
        )
        .all()
    )

    created_trips: list[Trip] = []

    for schedule in schedules:

        existing_trip = get_existing_schedule_trip(
            db=db,
            schedule_id=schedule.id,
            trip_date=trip_date,
        )

        if existing_trip is not None:
            continue

        service = get_service(
            db=db,
            service_id=schedule.service_id,
            university_id=university_id,
        )

        contract = get_service_contract(
            db=db,
            service=service,
        )

        try:
            validate_trip_contract_date(
                trip_date=trip_date,
                contract=contract,
            )
        except HTTPException:
            continue

        planned_departure_time = iran_datetime_to_utc(
            trip_date,
            schedule.departure_time,
        )

        try:
            check_duplicate_trip(
                db=db,
                service_id=service.id,
                trip_date=trip_date,
                planned_departure_time=planned_departure_time,
            )
        except HTTPException:
            continue

        trip = Trip(
            university_id=university_id,
            service_id=service.id,
            schedule_id=schedule.id,
            driver_id=None,
            vehicle_id=None,
            seated_capacity=None,
            standing_capacity=None,
            allow_standing=False,
            trip_date=trip_date,
            planned_departure_time=planned_departure_time,
            status="scheduled",
            is_active=True,
        )

        db.add(trip)
        created_trips.append(trip)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تولید سفرهای روزانه به دلیل ناسازگاری یا تکراری بودن اطلاعات کامل نشد",
        )

    for trip in created_trips:
        db.refresh(trip)

    return created_trips


# =========================================================
# Trip Assignment - Driver / Vehicle
# =========================================================

def assign_trip_resources(
    db: Session,
    trip: Trip,
    driver_id: int | None,
    vehicle_id: int | None,
) -> Trip:

    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تخصیص منابع به سفر غیرفعال وجود ندارد",
        )

    if trip.status not in {
        "scheduled",
        "boarding",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تخصیص راننده یا خودرو فقط قبل از شروع سفر امکان‌پذیر است",
        )

    if (
        driver_id is None
        and vehicle_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حداقل راننده یا خودرو باید مشخص شود",
        )

    service = (
        db.query(Service)
        .filter(
            Service.id == trip.service_id
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس سفر پیدا نشد",
        )

    contract = get_service_contract(
        db=db,
        service=service,
    )

    driver = None

    if driver_id is not None:
        driver = get_driver(
            db=db,
            driver_id=driver_id,
            university_id=trip.university_id,
        )

        validate_driver_contract_assignment(
            db=db,
            driver=driver,
            contract=contract,
            trip_date=trip.trip_date,
        )
    elif trip.driver_id is not None:
        driver = get_driver(
            db=db,
            driver_id=trip.driver_id,
            university_id=trip.university_id,
        )

    vehicle = None

    if vehicle_id is not None:
        vehicle = get_vehicle(
            db=db,
            vehicle_id=vehicle_id,
            university_id=trip.university_id,
        )

        validate_vehicle_contract_assignment(
            db=db,
            vehicle=vehicle,
            contract=contract,
            trip_date=trip.trip_date,
        )
    elif trip.vehicle_id is not None:
        vehicle = get_vehicle(
            db=db,
            vehicle_id=trip.vehicle_id,
            university_id=trip.university_id,
        )

    validate_driver_vehicle(
        driver=driver,
        vehicle=vehicle,
    )

    if driver is not None:
        check_resource_conflict(
            db=db,
            trip=trip,
            resource_field=Trip.driver_id,
            resource_id=driver.id,
            resource_name="راننده",
        )

    if vehicle is not None:
        check_resource_conflict(
            db=db,
            trip=trip,
            resource_field=Trip.vehicle_id,
            resource_id=vehicle.id,
            resource_name="خودرو",
        )

    if driver_id is not None:
        trip.driver_id = driver.id

    if vehicle_id is not None:
        trip.vehicle_id = vehicle.id

    if vehicle_id is not None and vehicle is not None:
        trip.seated_capacity = vehicle.capacity

    try:
        db.commit()
        db.refresh(trip)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تخصیص منابع به سفر به دلیل ناسازگاری اطلاعات انجام نشد",
        )

    return trip


# =========================================================
# Update Trip Status
# =========================================================

def update_trip_status(
    db: Session,
    trip: Trip,
    new_status: str,
) -> Trip:

    new_status = new_status.strip().lower()

    if new_status not in TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وضعیت جدید سفر نامعتبر است",
        )

    if (
        not trip.is_active
        and new_status != "cancelled"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سفر غیرفعال فقط می‌تواند لغو شود",
        )

    if new_status == "in_progress":

        if trip.driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای شروع سفر، راننده باید مشخص شده باشد",
            )

        if trip.vehicle_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای شروع سفر، خودرو باید مشخص شده باشد",
            )

    if new_status == "completed":

        if trip.actual_departure_time is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="سفر قبل از تکمیل باید شروع شده باشد",
            )

    validate_status_transition(
        current_status=trip.status,
        new_status=new_status,
    )

    apply_status_transition(
        trip=trip,
        new_status=new_status,
    )

    if new_status == "completed":
        process_trip_no_shows(
            db=db,
            trip=trip,
        )

    try:
        db.commit()
        db.refresh(trip)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تغییر وضعیت سفر به دلیل ناسازگاری اطلاعات انجام نشد",
        )

    return trip