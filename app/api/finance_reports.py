from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.roles import Roles
from app.database import get_db
from app.models.user import User
from app.services.finance_report_service import (
    get_contract_finance_summary,
    get_finance_report,
    get_transport_company_finance_summary,
    get_university_finance_summary,
)


router = APIRouter(
    prefix="/finance-reports",
    tags=["Finance Reports"],
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده گزارش‌های مالی را ندارید",
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد",
        )


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} نامعتبر است",
        )


def validate_university_access(
    current_user: User,
    university_id: int | None,
) -> None:
    if university_id is None:
        return

    validate_positive_id(
        university_id,
        "شناسه دانشگاه",
    )

    if (
        current_user.role != Roles.SUPER_ADMIN
        and current_user.university_id != university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به اطلاعات مالی این دانشگاه دسترسی ندارید",
        )


def validate_transport_company_access(
    current_user: User,
    transport_company_id: int | None,
) -> None:
    if transport_company_id is None:
        return

    validate_positive_id(
        transport_company_id,
        "شناسه شرکت حمل‌ونقل",
    )

    if current_user.role == Roles.SUPER_ADMIN:
        return

    if current_user.role == Roles.TRANSPORT_MANAGER:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="شما مجوز مشاهده اطلاعات این شرکت حمل‌ونقل را ندارید",
    )


@router.get("/")
def get_finance_reports(
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
    transport_company_id: int | None = Query(
        default=None,
        gt=0,
        description="شناسه شرکت حمل‌ونقل",
    ),
    contract_id: int | None = Query(
        default=None,
        gt=0,
        description="شناسه قرارداد",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_management_access(current_user)
    validate_date_range(start_date, end_date)
    validate_university_access(current_user, university_id)
    validate_transport_company_access(
        current_user,
        transport_company_id,
    )

    return get_finance_report(
        db,
        start_date=start_date,
        end_date=end_date,
        university_id=university_id,
        transport_company_id=transport_company_id,
        contract_id=contract_id,
    )


@router.get("/contract/{contract_id}")
def get_contract_finance_report(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_management_access(current_user)
    validate_positive_id(
        contract_id,
        "شناسه قرارداد",
    )

    report = get_contract_finance_summary(
        db,
        contract_id=contract_id,
    )

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="قرارداد موردنظر پیدا نشد",
        )

    validate_university_access(
        current_user,
        report["university_id"],
    )

    return report


@router.get("/university/{university_id}")
def get_university_finance_report(
    university_id: int,
    start_date: date | None = Query(
        default=None,
        description="تاریخ شروع گزارش",
    ),
    end_date: date | None = Query(
        default=None,
        description="تاریخ پایان گزارش",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_management_access(current_user)
    validate_positive_id(
        university_id,
        "شناسه دانشگاه",
    )
    validate_date_range(
        start_date,
        end_date,
    )
    validate_university_access(
        current_user,
        university_id,
    )

    return get_university_finance_summary(
        db,
        university_id=university_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/transport-company/{transport_company_id}")
def get_transport_company_finance_report(
    transport_company_id: int,
    start_date: date | None = Query(
        default=None,
        description="تاریخ شروع گزارش",
    ),
    end_date: date | None = Query(
        default=None,
        description="تاریخ پایان گزارش",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    validate_management_access(current_user)
    validate_positive_id(
        transport_company_id,
        "شناسه شرکت حمل‌ونقل",
    )
    validate_date_range(
        start_date,
        end_date,
    )
    validate_transport_company_access(
        current_user,
        transport_company_id,
    )

    return get_transport_company_finance_summary(
        db,
        transport_company_id=transport_company_id,
        start_date=start_date,
        end_date=end_date,
    )