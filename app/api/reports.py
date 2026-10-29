from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User

from app.schemas.report import (
    TransportSummaryReport,
    FinancialReport,
    RouteUsageReportItem,
    DriverPerformanceReportItem,
    VehicleUsageReportItem,
)

from app.core.dependencies import (
    get_current_user,
)

from app.core.roles import (
    Roles,
    MANAGEMENT_ROLES,
)

from app.services.report_service import (
    get_transport_summary,
    get_financial_report,
    get_route_usage_report,
    get_driver_performance_report,
    get_vehicle_usage_report,
)


router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


REPORT_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


def get_report_university_id(
    current_user: User,
    university_id: int | None,
) -> int:
    if current_user.role == Roles.SUPER_ADMIN:
        if university_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای مدیر کل تعیین دانشگاه الزامی است",
            )

        return university_id

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست",
        )

    if (
        university_id is not None
        and university_id != current_user.university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به گزارش‌های این دانشگاه دسترسی ندارید",
        )

    return current_user.university_id


def validate_report_access(
    current_user: User,
) -> None:
    if current_user.role not in REPORT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده گزارش‌ها را ندارید",
        )


@router.get(
    "/summary",
    response_model=TransportSummaryReport,
)
def transport_summary_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    university_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_report_access(current_user)

    university_id = get_report_university_id(
        current_user,
        university_id,
    )

    return get_transport_summary(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/financial",
    response_model=FinancialReport,
)
def financial_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    university_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_report_access(current_user)

    university_id = get_report_university_id(
        current_user,
        university_id,
    )

    return get_financial_report(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/routes",
    response_model=list[RouteUsageReportItem],
)
def route_usage_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    university_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_report_access(current_user)

    university_id = get_report_university_id(
        current_user,
        university_id,
    )

    return get_route_usage_report(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/drivers",
    response_model=list[DriverPerformanceReportItem],
)
def driver_performance_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    university_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_report_access(current_user)

    university_id = get_report_university_id(
        current_user,
        university_id,
    )

    return get_driver_performance_report(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/vehicles",
    response_model=list[VehicleUsageReportItem],
)
def vehicle_usage_report(
    from_date: date = Query(...),
    to_date: date = Query(...),
    university_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_report_access(current_user)

    university_id = get_report_university_id(
        current_user,
        university_id,
    )

    return get_vehicle_usage_report(
        db,
        university_id=university_id,
        from_date=from_date,
        to_date=to_date,
    )
