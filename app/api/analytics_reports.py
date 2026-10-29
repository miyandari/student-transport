from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.database import get_db
from app.models.user import User
from app.services.analytics_report_service import get_analytics_report


router = APIRouter(
    prefix="/analytics-reports",
    tags=["Analytics Reports"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}


def validate_management_access(
    current_user: User,
) -> None:
    if current_user.role not in MANAGEMENT_ROLES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده گزارش‌های آماری را ندارید",
        )


def validate_university_access(
    current_user: User,
    university_id: int | None,
) -> None:
    if university_id is None:
        return

    if (
        current_user.role != Roles.SUPER_ADMIN
        and current_user.university_id != university_id
    ):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به اطلاعات آماری این دانشگاه دسترسی ندارید",
        )


def validate_date_range(
    start_date: date | None,
    end_date: date | None,
) -> None:
    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد",
        )


@router.get("/")
def get_analytics_reports(
    start_date: date | None = Query(
        default=None,
        description="تاریخ شروع گزارش",
    ),
    end_date: date | None = Query(
        default=None,
        description="تاریخ پایان گزارش",
    ),
    university_id: int | None = Query(
        default=None,
        gt=0,
        description="شناسه دانشگاه",
    ),
    service_id: int | None = Query(
        default=None,
        gt=0,
        description="شناسه سرویس",
    ),
    route_id: int | None = Query(
        default=None,
        gt=0,
        description="شناسه مسیر",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_management_access(current_user)
    validate_date_range(
        start_date,
        end_date,
    )
    validate_university_access(
        current_user,
        university_id,
    )

    return get_analytics_report(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
        service_id=service_id,
        route_id=route_id,
    )