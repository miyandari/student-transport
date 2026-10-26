from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.university import University
from app.models.user import User
from app.schemas.university import (
    UniversityCreate,
    UniversityResponse,
)
from app.core.dependencies import require_roles
from app.core.roles import Roles


router = APIRouter(
    prefix="/universities",
    tags=["Universities"]
)


# =========================================================
# ایجاد دانشگاه
# فقط مدیر کل
# =========================================================

@router.post(
    "/",
    response_model=UniversityResponse,
    status_code=status.HTTP_201_CREATED
)
def create_university(
    university_data: UniversityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(Roles.SUPER_ADMIN)
    ),
):
    name = university_data.name.strip()
    code = university_data.code.strip()

    # --------------------------------
    # کنترل اطلاعات ورودی
    # --------------------------------

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام دانشگاه نمی‌تواند خالی باشد"
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="کد دانشگاه نمی‌تواند خالی باشد"
        )

    # --------------------------------
    # کد دانشگاه تکراری نباشد
    # --------------------------------

    existing_university = (
        db.query(University)
        .filter(
            University.code == code
        )
        .first()
    )

    if existing_university:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این کد دانشگاه قبلاً ثبت شده است"
        )

    # --------------------------------
    # ایجاد دانشگاه
    # --------------------------------

    university = University(
        name=name,
        code=code,
        is_active=university_data.is_active,
    )

    db.add(university)
    db.commit()
    db.refresh(university)

    return university


# =========================================================
# مشاهده دانشگاه‌ها
# =========================================================

@router.get(
    "/",
    response_model=list[UniversityResponse]
)
def get_universities(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            Roles.SUPER_ADMIN,
            Roles.UNIVERSITY_ADMIN,
        )
    ),
):
    # --------------------------------
    # مدیر کل
    # دسترسی به همه دانشگاه‌ها
    # --------------------------------

    if current_user.role == Roles.SUPER_ADMIN:

        return (
            db.query(University)
            .order_by(University.id)
            .all()
        )

    # --------------------------------
    # مدیر دانشگاه
    # --------------------------------

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست"
        )

    university = (
        db.query(University)
        .filter(
            University.id == current_user.university_id
        )
        .first()
    )

    if university is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشگاه مرتبط با حساب کاربری پیدا نشد"
        )

    return [university]