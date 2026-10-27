from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.transport_company import TransportCompany
from app.models.user import User
from app.schemas.transport_company import (
    TransportCompanyCreate,
    TransportCompanyResponse,
    TransportCompanyStatusUpdate,
)
from app.core.dependencies import get_current_user
from app.core.roles import Roles


router = APIRouter(
    prefix="/transport-companies",
    tags=["Transport Companies"],
)


VIEW_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
}


def check_super_admin(
    current_user: User,
) -> None:

    if current_user.role != Roles.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مدیر سامانه مجوز مدیریت شرکت‌های حمل‌ونقل را دارد",
        )


def check_view_role(
    current_user: User,
) -> None:

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده شرکت‌های حمل‌ونقل را ندارید",
        )


def get_company_or_404(
    db: Session,
    company_id: int,
) -> TransportCompany:

    if company_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه شرکت نامعتبر است",
        )

    company = (
        db.query(TransportCompany)
        .filter(
            TransportCompany.id == company_id,
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="شرکت حمل‌ونقل پیدا نشد",
        )

    return company


def normalize_text(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    value = value.strip()

    return value if value else None


def validate_company_name(
    name: str | None,
) -> str:

    if name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام شرکت الزامی است",
        )

    name = name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام شرکت نمی‌تواند خالی باشد",
        )

    return name


@router.post(
    "/",
    response_model=TransportCompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transport_company(
    data: TransportCompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_super_admin(
        current_user,
    )

    name = validate_company_name(
        data.name,
    )

    registration_number = normalize_text(
        data.registration_number,
    )

    if registration_number:
        existing = (
            db.query(TransportCompany)
            .filter(
                TransportCompany.registration_number
                == registration_number,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شماره ثبت شرکت قبلاً ثبت شده است",
            )

    company = TransportCompany(
        name=name,
        registration_number=registration_number,
        phone=normalize_text(data.phone),
        address=normalize_text(data.address),
        is_active=data.is_active,
    )

    db.add(company)

    try:
        db.commit()
        db.refresh(company)
    except Exception:
        db.rollback()
        raise

    return company


@router.get(
    "/",
    response_model=list[TransportCompanyResponse],
)
def get_transport_companies(
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user,
    )

    # مدیر شرکت فقط شرکت خودش را مشاهده می‌کند.
    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به شرکت حمل‌ونقل متصل نیست",
            )

        query = (
            db.query(TransportCompany)
            .filter(
                TransportCompany.id
                == current_user.transport_company_id,
            )
        )

        if is_active is not None:
            query = query.filter(
                TransportCompany.is_active == is_active,
            )

        return query.all()

    query = db.query(TransportCompany)

    if is_active is not None:
        query = query.filter(
            TransportCompany.is_active == is_active,
        )

    return (
        query
        .order_by(
            TransportCompany.id.desc(),
        )
        .all()
    )


@router.get(
    "/my-company",
    response_model=TransportCompanyResponse,
)
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role != Roles.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این بخش فقط برای مدیر شرکت حمل‌ونقل است",
        )

    if current_user.transport_company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به شرکت حمل‌ونقل متصل نیست",
        )

    return get_company_or_404(
        db,
        current_user.transport_company_id,
    )


@router.get(
    "/{company_id}",
    response_model=TransportCompanyResponse,
)
def get_transport_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط به شرکت خود دسترسی دارید",
            )

    return get_company_or_404(
        db,
        company_id,
    )


@router.patch(
    "/{company_id}",
    response_model=TransportCompanyResponse,
)
def update_transport_company(
    company_id: int,
    data: TransportCompanyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_super_admin(
        current_user,
    )

    company = get_company_or_404(
        db,
        company_id,
    )

    name = validate_company_name(
        data.name,
    )

    registration_number = normalize_text(
        data.registration_number,
    )

    if registration_number:
        duplicate = (
            db.query(TransportCompany)
            .filter(
                TransportCompany.registration_number
                == registration_number,
                TransportCompany.id != company_id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شماره ثبت شرکت قبلاً برای شرکت دیگری ثبت شده است",
            )

    company.name = name
    company.registration_number = registration_number
    company.phone = normalize_text(data.phone)
    company.address = normalize_text(data.address)
    company.is_active = data.is_active

    try:
        db.commit()
        db.refresh(company)
    except Exception:
        db.rollback()
        raise

    return company


@router.patch(
    "/{company_id}/status",
    response_model=TransportCompanyResponse,
)
def update_transport_company_status(
    company_id: int,
    data: TransportCompanyStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_super_admin(
        current_user,
    )

    company = get_company_or_404(
        db,
        company_id,
    )

    company.is_active = data.is_active

    try:
        db.commit()
        db.refresh(company)
    except Exception:
        db.rollback()
        raise

    return company