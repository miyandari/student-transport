from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.models.service import Service


def get_schedule(
    db: Session,
    schedule_id: int,
) -> Schedule:
    if schedule_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه برنامه زمانی نامعتبر است",
        )

    schedule = (
        db.query(Schedule)
        .filter(Schedule.id == schedule_id)
        .first()
    )

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برنامه زمانی پیدا نشد",
        )

    return schedule


def get_service(
    db: Session,
    service_id: int,
) -> Service:
    if service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
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

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس موردنظر غیرفعال است",
        )

    return service


def validate_day_of_week(
    day_of_week: int,
) -> None:
    if day_of_week < 0 or day_of_week > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="روز هفته باید عددی بین 0 تا 6 باشد",
        )


def validate_times(
    departure_time,
    arrival_time,
) -> None:
    if arrival_time is not None and arrival_time <= departure_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان رسیدن باید بعد از زمان حرکت باشد",
        )


def normalize_schedule_type(
    schedule_type: str,
) -> str:
    if schedule_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع برنامه زمانی نمی‌تواند خالی باشد",
        )

    schedule_type = schedule_type.strip()

    if not schedule_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع برنامه زمانی نمی‌تواند خالی باشد",
        )

    if len(schedule_type) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع برنامه زمانی بیش از حد مجاز طولانی است",
        )

    return schedule_type


def validate_service_university(
    service: Service,
    university_id: int,
) -> None:
    if university_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه دانشگاه نامعتبر است",
        )

    if service.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس متعلق به دانشگاه انتخاب‌شده نیست",
        )


def check_duplicate_schedule(
    db: Session,
    *,
    service_id: int,
    day_of_week: int,
    departure_time,
    schedule_id: int | None = None,
) -> None:
    query = (
        db.query(Schedule)
        .filter(
            Schedule.service_id == service_id,
            Schedule.day_of_week == day_of_week,
            Schedule.departure_time == departure_time,
            Schedule.is_active.is_(True),
        )
    )

    if schedule_id is not None:
        query = query.filter(
            Schedule.id != schedule_id
        )

    existing = query.first()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "برای این سرویس در این روز و ساعت، "
                "برنامه زمانی فعال دیگری وجود دارد"
            ),
        )


def create_schedule(
    db: Session,
    *,
    university_id: int,
    service_id: int,
    day_of_week: int,
    departure_time,
    arrival_time,
    schedule_type: str,
    is_active: bool,
) -> Schedule:

    validate_day_of_week(day_of_week)

    validate_times(
        departure_time,
        arrival_time,
    )

    schedule_type = normalize_schedule_type(
        schedule_type
    )

    service = get_service(
        db,
        service_id,
    )

    validate_service_university(
        service,
        university_id,
    )

    if is_active:
        check_duplicate_schedule(
            db,
            service_id=service_id,
            day_of_week=day_of_week,
            departure_time=departure_time,
        )

    schedule = Schedule(
        university_id=university_id,
        service_id=service_id,
        day_of_week=day_of_week,
        departure_time=departure_time,
        arrival_time=arrival_time,
        schedule_type=schedule_type,
        is_active=is_active,
    )

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return schedule


def get_schedules(
    db: Session,
    *,
    university_id: int | None = None,
    service_id: int | None = None,
    day_of_week: int | None = None,
    is_active: bool | None = None,
) -> list[Schedule]:

    if university_id is not None:
        if university_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه دانشگاه نامعتبر است",
            )

    if service_id is not None:
        if service_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شناسه سرویس نامعتبر است",
            )

    if day_of_week is not None:
        validate_day_of_week(day_of_week)

    query = db.query(Schedule)

    if university_id is not None:
        query = query.filter(
            Schedule.university_id == university_id
        )

    if service_id is not None:
        query = query.filter(
            Schedule.service_id == service_id
        )

    if is_active is not None:
        query = query.filter(
            Schedule.is_active == is_active
        )

    if day_of_week is not None:
        query = query.filter(
            Schedule.day_of_week == day_of_week
        )

    return (
        query
        .order_by(
            Schedule.day_of_week,
            Schedule.departure_time,
        )
        .all()
    )


def update_schedule(
    db: Session,
    *,
    schedule_id: int,
    university_id: int,
    service_id: int,
    day_of_week: int,
    departure_time,
    arrival_time,
    schedule_type: str,
    is_active: bool,
) -> Schedule:

    schedule = get_schedule(
        db,
        schedule_id,
    )

    if schedule.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه برنامه زمانی وجود ندارد",
        )

    validate_day_of_week(day_of_week)

    validate_times(
        departure_time,
        arrival_time,
    )

    schedule_type = normalize_schedule_type(
        schedule_type
    )

    service = get_service(
        db,
        service_id,
    )

    validate_service_university(
        service,
        university_id,
    )

    if is_active:
        check_duplicate_schedule(
            db,
            service_id=service_id,
            day_of_week=day_of_week,
            departure_time=departure_time,
            schedule_id=schedule.id,
        )

    schedule.service_id = service_id
    schedule.day_of_week = day_of_week
    schedule.departure_time = departure_time
    schedule.arrival_time = arrival_time
    schedule.schedule_type = schedule_type
    schedule.is_active = is_active

    db.commit()
    db.refresh(schedule)

    return schedule


def update_schedule_status(
    db: Session,
    *,
    schedule_id: int,
    is_active: bool,
) -> Schedule:

    schedule = get_schedule(
        db,
        schedule_id,
    )

    if is_active:
        get_service(
            db,
            schedule.service_id,
        )

        check_duplicate_schedule(
            db,
            service_id=schedule.service_id,
            day_of_week=schedule.day_of_week,
            departure_time=schedule.departure_time,
            schedule_id=schedule.id,
        )

    schedule.is_active = is_active

    db.commit()
    db.refresh(schedule)

    return schedule