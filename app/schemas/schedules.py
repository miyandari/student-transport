from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schedule import Schedule
from app.models.service import Service
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.core.dependencies import get_current_user
from app.models.user import User
from app.core.roles import Roles


router = APIRouter(
    prefix="/schedules",
    tags=["Schedules"]
)


@router.post(
    "/",
    response_model=ScheduleResponse
)
def create_schedule(
    data: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [
        Roles.SUPER_ADMIN,
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت برنامه زمانی را ندارید"
        )

    if data.day_of_week < 0 or data.day_of_week > 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="روز هفته باید عددی بین 0 تا 6 باشد"
        )

    service = (
        db.query(Service)
        .filter(Service.id == data.service_id)
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سرویس موردنظر پیدا نشد"
        )

    if service.university_id != data.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس متعلق به دانشگاه انتخاب‌شده نیست"
        )

    if current_user.role != Roles.SUPER_ADMIN:
        if current_user.university_id != data.university_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما به اطلاعات این دانشگاه دسترسی ندارید"
            )

    schedule = Schedule(
        university_id=data.university_id,
        service_id=data.service_id,
        day_of_week=data.day_of_week,
        departure_time=data.departure_time,
        arrival_time=data.arrival_time,
        schedule_type=data.schedule_type,
        is_active=data.is_active
    )

    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return schedule


@router.get(
    "/",
    response_model=list[ScheduleResponse]
)
def get_schedules(
    service_id: int | None = None,
    day_of_week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [
        Roles.SUPER_ADMIN,
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده برنامه‌های زمانی را ندارید"
        )

    query = db.query(Schedule)

    if current_user.role != Roles.SUPER_ADMIN:
        query = query.filter(
            Schedule.university_id == current_user.university_id
        )

    if service_id is not None:
        query = query.filter(
            Schedule.service_id == service_id
        )

    if day_of_week is not None:
        if day_of_week < 0 or day_of_week > 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="روز هفته باید عددی بین 0 تا 6 باشد"
            )

        query = query.filter(
            Schedule.day_of_week == day_of_week
        )

    return (
        query
        .order_by(
            Schedule.day_of_week,
            Schedule.departure_time
        )
        .all()
    )