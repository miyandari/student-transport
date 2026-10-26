from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.service import Service
from app.models.schedule import Schedule
from app.models.contract import Contract
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_company_user,
    check_company_contract_access,
)
from app.core.roles import Roles

from app.services.schedule_service import (
    get_schedule,
    create_schedule,
    get_schedules,
    update_schedule,
    update_schedule_status,
)


router = APIRouter(
    prefix="/schedules",
    tags=["Schedules"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
}


VIEW_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
    Roles.DRIVER,
    Roles.STUDENT,
}


def check_management_role(
    current_user: User,
) -> None:
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت برنامه زمانی را ندارید",
        )


def check_view_role(
    current_user: User,
) -> None:
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده برنامه‌های زمانی را ندارید",
        )


def get_schedule_or_404(
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
        .filter(
            Schedule.id == schedule_id,
        )
        .first()
    )

    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برنامه زمانی موردنظر پیدا نشد",
        )

    return schedule


def get_active_service(
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
        .filter(
            Service.id == service_id,
            Service.is_active.is_(True),
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس موردنظر پیدا نشد یا غیرفعال است",
        )

    return service


def check_company_service_access(
    db: Session,
    current_user: User,
    service: Service,
) -> Contract:
    check_company_user(current_user)

    if service.contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس تحت قرارداد شرکت قرار ندارد",
        )

    contract = check_company_contract_access(
        db=db,
        current_user=current_user,
        contract_id=service.contract_id,
    )

    if contract.university_id != service.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="اطلاعات سرویس و قرارداد با یکدیگر سازگار نیستند",
        )

    return contract


def check_schedule_company_access(
    db: Session,
    current_user: User,
    schedule: Schedule,
) -> Service:
    if schedule.service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس برنامه زمانی نامعتبر است",
        )

    service = (
        db.query(Service)
        .filter(
            Service.id == schedule.service_id,
            Service.is_active.is_(True),
        )
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس برنامه زمانی پیدا نشد یا غیرفعال است",
        )

    if service.university_id != schedule.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه برنامه زمانی و سرویس یکسان نیستند",
        )

    check_company_service_access(
        db,
        current_user,
        service,
    )

    return service


def validate_service_for_schedule(
    db: Session,
    current_user: User,
    university_id: int,
    service_id: int,
) -> Service:
    if university_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه دانشگاه نامعتبر است",
        )

    service = get_active_service(
        db,
        service_id,
    )

    if service.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس انتخاب‌شده متعلق به این دانشگاه نیست",
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_service_access(
            db,
            current_user,
            service,
        )
    else:
        check_university_access(
            current_user,
            university_id,
        )

    return service


@router.post(
    "/",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule_endpoint(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    validate_service_for_schedule(
        db,
        current_user,
        data.university_id,
        data.service_id,
    )

    return create_schedule(
        db,
        university_id=data.university_id,
        service_id=data.service_id,
        day_of_week=data.day_of_week,
        departure_time=data.departure_time,
        arrival_time=data.arrival_time,
        schedule_type=data.schedule_type,
        is_active=data.is_active,
    )


@router.get(
    "/",
    response_model=list[ScheduleResponse],
)
def get_schedules_endpoint(
    service_id: int | None = None,
    day_of_week: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_view_role(current_user)

    if service_id is not None and service_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سرویس نامعتبر است",
        )

    if day_of_week is not None and not 0 <= day_of_week <= 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="روز هفته نامعتبر است",
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_user(current_user)

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شرکت به شرکت حمل‌ونقلی متصل نیست",
            )

        query = (
            db.query(Schedule)
            .join(
                Service,
                Service.id == Schedule.service_id,
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
            )
        )

        if service_id is not None:
            query = query.filter(
                Schedule.service_id == service_id
            )

        if day_of_week is not None:
            query = query.filter(
                Schedule.day_of_week == day_of_week
            )

        if is_active is not None:
            query = query.filter(
                Schedule.is_active == is_active
            )

        return (
            query
            .order_by(
                Schedule.day_of_week,
                Schedule.departure_time,
            )
            .all()
        )

    if current_user.role == Roles.SUPER_ADMIN:
        university_id = None
    else:
        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        university_id = current_user.university_id

    return get_schedules(
        db,
        university_id=university_id,
        service_id=service_id,
        day_of_week=day_of_week,
        is_active=is_active,
    )


@router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
)
def get_schedule_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_view_role(current_user)

    schedule = get_schedule_or_404(
        db,
        schedule_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_schedule_company_access(
            db,
            current_user,
            schedule,
        )
    else:
        check_university_access(
            current_user,
            schedule.university_id,
        )

    return schedule


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleResponse,
)
def update_schedule_endpoint(
    schedule_id: int,
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    schedule = get_schedule_or_404(
        db,
        schedule_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        check_schedule_company_access(
            db,
            current_user,
            schedule,
        )

        if data.university_id != schedule.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="امکان تغییر دانشگاه برنامه زمانی وجود ندارد",
            )

        validate_service_for_schedule(
            db,
            current_user,
            data.university_id,
            data.service_id,
        )

    else:
        check_university_access(
            current_user,
            schedule.university_id,
        )

        if data.university_id != schedule.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="امکان تغییر دانشگاه برنامه زمانی وجود ندارد",
            )

        validate_service_for_schedule(
            db,
            current_user,
            data.university_id,
            data.service_id,
        )

    return update_schedule(
        db,
        schedule_id=schedule_id,
        university_id=data.university_id,
        service_id=data.service_id,
        day_of_week=data.day_of_week,
        departure_time=data.departure_time,
        arrival_time=data.arrival_time,
        schedule_type=data.schedule_type,
        is_active=data.is_active,
    )


@router.patch(
    "/{schedule_id}/status",
    response_model=ScheduleResponse,
)
def update_schedule_status_endpoint(
    schedule_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_management_role(current_user)

    schedule = get_schedule_or_404(
        db,
        schedule_id,
    )

    if current_user.role == Roles.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تغییر وضعیت فعال/غیرفعال برنامه زمانی فقط توسط مدیریت دانشگاه انجام می‌شود",
        )

    check_university_access(
        current_user,
        schedule.university_id,
    )

    return update_schedule_status(
        db,
        schedule_id=schedule_id,
        is_active=is_active,
    )
