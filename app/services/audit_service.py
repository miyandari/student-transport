from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def create_audit_log(
    db: Session,
    *,
    user: User | None = None,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    description: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """
    ثبت یک رویداد مدیریتی یا عملیاتی در Audit Log.

    این تابع باید نقطه مرکزی ثبت تمام تغییرات مهم سامانه باشد.
    """

    university_id = None
    transport_company_id = None
    user_id = None

    if user is not None:
        user_id = user.id
        university_id = user.university_id
        transport_company_id = user.transport_company_id

    audit_log = AuditLog(
        user_id=user_id,
        university_id=university_id,
        transport_company_id=transport_company_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(audit_log)
    db.flush()

    return audit_log