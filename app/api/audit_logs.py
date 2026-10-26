from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.core.dependencies import get_current_user
from app.core.roles import Roles


router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


AUDIT_VIEW_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
}


@router.get(
    "/",
    response_model=list[AuditLogResponse],
)
def get_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    university_id: int | None = None,
    transport_company_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in AUDIT_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده گزارش‌های سیستمی را ندارید",
        )

    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="skip نمی‌تواند منفی باشد",
        )

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit باید بین 1 تا 500 باشد",
        )

    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد",
        )

    query = db.query(AuditLog)

    # ---------------------------------------------------------
    # Super Admin
    # ---------------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:

        if university_id is not None:
            query = query.filter(
                AuditLog.university_id == university_id
            )

        if transport_company_id is not None:
            query = query.filter(
                AuditLog.transport_company_id
                == transport_company_id
            )

    # ---------------------------------------------------------
    # University Admin / Transport Manager
    # ---------------------------------------------------------

    elif current_user.role in {
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
    }:

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
                detail="شما مجاز به مشاهده لاگ‌های این دانشگاه نیستید",
            )

        query = query.filter(
            AuditLog.university_id
            == current_user.university_id
        )

        if transport_company_id is not None:
            query = query.filter(
                AuditLog.transport_company_id
                == transport_company_id
            )

    # ---------------------------------------------------------
    # Company Admin
    # ---------------------------------------------------------

    elif current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب شرکت شما به شرکت حمل‌ونقل متصل نیست",
            )

        if (
            transport_company_id is not None
            and transport_company_id
            != current_user.transport_company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما مجاز به مشاهده لاگ‌های شرکت دیگری نیستید",
            )

        query = query.filter(
            AuditLog.transport_company_id
            == current_user.transport_company_id
        )

        if university_id is not None:
            query = query.filter(
                AuditLog.university_id == university_id
            )

    # ---------------------------------------------------------
    # Common filters
    # ---------------------------------------------------------

    if action is not None:
        query = query.filter(
            AuditLog.action == action
        )

    if entity_type is not None:
        query = query.filter(
            AuditLog.entity_type == entity_type
        )

    if entity_id is not None:
        query = query.filter(
            AuditLog.entity_id == entity_id
        )

    if user_id is not None:
        query = query.filter(
            AuditLog.user_id == user_id
        )

    if start_date is not None:
        query = query.filter(
            AuditLog.created_at >= start_date
        )

    if end_date is not None:
        query = query.filter(
            AuditLog.created_at <= end_date
        )

    return (
        query
        .order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogResponse,
)
def get_audit_log(
    audit_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in AUDIT_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده گزارش‌های سیستمی را ندارید",
        )

    audit_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.id == audit_log_id
        )
        .first()
    )

    if audit_log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گزارش موردنظر پیدا نشد",
        )

    # ---------------------------------------------------------
    # Access control
    # ---------------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:
        return audit_log

    if current_user.role in {
        Roles.UNIVERSITY_ADMIN,
        Roles.TRANSPORT_MANAGER,
    }:

        if (
            current_user.university_id is None
            or audit_log.university_id
            != current_user.university_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما مجاز به مشاهده این گزارش نیستید",
            )

        return audit_log

    if current_user.role == Roles.COMPANY_ADMIN:

        if (
            current_user.transport_company_id is None
            or audit_log.transport_company_id
            != current_user.transport_company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما مجاز به مشاهده این گزارش نیستید",
            )

        return audit_log

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="شما مجوز مشاهده این گزارش را ندارید",
    )