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


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}


def get_company_or_404(
    db: Session,
    company_id: int,
):
    company = (
        db.query(TransportCompany)
        .filter(
            TransportCompany.id == company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="شرکت حمل‌ونقل پیدا نشد",
        )

    return company


def normalize_text(value: str | None):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


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
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد شرکت حمل‌ونقل را ندارید",
        )

    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام شرکت نمی‌تواند خالی باشد",
        )

    registration_number = normalize_text(
        data.registration_number
    )

    if registration_number:
        existing = (
            db.query(TransportCompany)
            .filter(
                TransportCompany.registration_number
                == registration_number
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
    db.commit()
    db.refresh(company)

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
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده فهرست شرکت‌ها را ندارید",
        )

    query = db.query(TransportCompany)

    if is_active is not None:
        query = query.filter(
            TransportCompany.is_active == is_active
        )

    return (
        query
        .order_by(TransportCompany.id.desc())
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

    company = get_company_or_404(
        db,
        current_user.transport_company_id,
    )

    return company


@router.get(
    "/{company_id}",
    response_model=TransportCompanyResponse,
)
def get_transport_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط به شرکت خود دسترسی دارید",
            )

    elif current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده شرکت را ندارید",
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
    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط می‌توانید اطلاعات شرکت خود را ویرایش کنید",
            )

    elif current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش اطلاعات شرکت را ندارید",
        )

    company = get_company_or_404(
        db,
        company_id,
    )

    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام شرکت نمی‌تواند خالی باشد",
        )

    registration_number = normalize_text(
        data.registration_number
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

    # شرکت نمی‌تواند از داخل حساب خودش وضعیت فعال/غیرفعال را تغییر دهد.
    if current_user.role in MANAGEMENT_ROLES:
        company.is_active = data.is_active

    db.commit()
    db.refresh(company)

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
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مدیریت دانشگاه می‌تواند وضعیت شرکت را تغییر دهد",
        )

    company = get_company_or_404(
        db,
        company_id,
    )

    company.is_active = data.is_active

    db.commit()
    db.refresh(company)

    return company