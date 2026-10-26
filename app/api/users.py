from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.user import User
from app.models.student import Student
from app.models.driver import Driver
from app.models.university import University
from app.models.transport_company import TransportCompany

from app.schemas.auth import UserCreate
from app.schemas.user import (
    UserProfileResponse,
    ChangeMyPasswordRequest,
    ChangeUserPasswordRequest,
    UserStatusResponse,
)

from app.core.security import hash_password, verify_password
from app.core.dependencies import get_current_user
from app.core.roles import Roles, ALL_ROLES


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
}


def get_user_or_404(
    db: Session,
    user_id: int,
):
    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="کاربر پیدا نشد",
        )

    return user


def check_user_management_access(
    current_user: User,
    target_user: User,
):
    if current_user.role == Roles.SUPER_ADMIN:
        return

    if current_user.role == Roles.UNIVERSITY_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        if (
            target_user.university_id
            != current_user.university_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما به این کاربر دسترسی ندارید",
            )

        if target_user.role == Roles.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما نمی‌توانید به حساب مدیر کل دسترسی مدیریتی داشته باشید",
            )

        if target_user.role == Roles.COMPANY_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما نمی‌توانید به حساب مدیر شرکت دسترسی مدیریتی داشته باشید",
            )

        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="شما مجوز مدیریت این کاربر را ندارید",
    )


def get_active_university(
    db: Session,
    university_id: int,
):
    university = (
        db.query(University)
        .filter(
            University.id == university_id
        )
        .first()
    )

    if university is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشگاه پیدا نشد",
        )

    if not university.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه انتخاب‌شده فعال نیست",
        )

    return university


def get_active_transport_company(
    db: Session,
    transport_company_id: int,
):
    company = (
        db.query(TransportCompany)
        .filter(
            TransportCompany.id == transport_company_id
        )
        .first()
    )

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="شرکت حمل‌ونقل پیدا نشد",
        )

    if not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شرکت حمل‌ونقل انتخاب‌شده فعال نیست",
        )

    return company


# =========================================================
# ایجاد کاربر
# =========================================================

@router.post(
    "/",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد کاربر ندارید",
        )

    username = user_data.username.strip()

    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام کاربری نمی‌تواند خالی باشد",
        )

    existing_user = (
        db.query(User)
        .filter(
            User.username == username
        )
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این نام کاربری قبلاً ثبت شده است",
        )

    if user_data.role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نقش کاربر نامعتبر است",
        )

    target_role = user_data.role

    # =====================================================
    # SUPER ADMIN
    # =====================================================

    if target_role == Roles.SUPER_ADMIN:

        if current_user.role != Roles.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط مدیر کل می‌تواند مدیر کل دیگری ایجاد کند",
            )

        if user_data.university_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر کل نباید به دانشگاه متصل باشد",
            )

        if user_data.transport_company_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر کل نباید به شرکت حمل‌ونقل متصل باشد",
            )

        if user_data.student_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر کل نباید به دانشجو متصل باشد",
            )

        if user_data.driver_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر کل نباید به راننده متصل باشد",
            )

    # =====================================================
    # COMPANY ADMIN
    # =====================================================

    elif target_role == Roles.COMPANY_ADMIN:

        if current_user.role != Roles.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="فقط مدیر کل می‌تواند مدیر شرکت ایجاد کند",
            )

        if user_data.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای مدیر شرکت، تعیین شرکت حمل‌ونقل الزامی است",
            )

        if user_data.university_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر شرکت نباید مستقیماً به دانشگاه متصل باشد",
            )

        if user_data.student_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر شرکت نباید به دانشجو متصل باشد",
            )

        if user_data.driver_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="مدیر شرکت نباید به راننده متصل باشد",
            )

        get_active_transport_company(
            db,
            user_data.transport_company_id,
        )

    # =====================================================
    # سایر نقش‌ها
    # =====================================================

    else:

        if user_data.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای این نقش تعیین دانشگاه الزامی است",
            )

        if user_data.transport_company_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این نقش نباید مستقیماً به شرکت حمل‌ونقل متصل باشد",
            )

        get_active_university(
            db,
            user_data.university_id,
        )

        # -------------------------------------------------
        # محدودیت مدیر دانشگاه
        # -------------------------------------------------

        if current_user.role == Roles.UNIVERSITY_ADMIN:

            if (
                current_user.university_id
                != user_data.university_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="شما فقط می‌توانید برای دانشگاه خودتان کاربر ایجاد کنید",
                )

            if target_role == Roles.UNIVERSITY_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="مدیر دانشگاه نمی‌تواند مدیر دانشگاه دیگری ایجاد کند",
                )

            if target_role == Roles.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="مدیر دانشگاه نمی‌تواند مدیر کل ایجاد کند",
                )

            if target_role == Roles.COMPANY_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ایجاد مدیر شرکت فقط توسط مدیر کل انجام می‌شود",
                )

    # =====================================================
    # حساب دانشجو
    # =====================================================

    if target_role == Roles.STUDENT:

        if user_data.student_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای حساب دانشجویی، انتخاب دانشجو الزامی است",
            )

        if user_data.driver_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="حساب دانشجویی نمی‌تواند به راننده متصل باشد",
            )

        student = (
            db.query(Student)
            .filter(
                Student.id == user_data.student_id
            )
            .first()
        )

        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="دانشجو پیدا نشد",
            )

        if not student.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="دانشجوی انتخاب‌شده فعال نیست",
            )

        if student.university_id != user_data.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="دانشجو متعلق به دانشگاه انتخاب‌شده نیست",
            )

        existing_student_user = (
            db.query(User)
            .filter(
                User.student_id == student.id
            )
            .first()
        )

        if existing_student_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این دانشجو قبلاً دارای حساب کاربری است",
            )

    # =====================================================
    # حساب راننده
    # =====================================================

    elif target_role == Roles.DRIVER:

        if user_data.driver_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای حساب راننده، انتخاب راننده الزامی است",
            )

        if user_data.student_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="حساب راننده نمی‌تواند به دانشجو متصل باشد",
            )

        driver = (
            db.query(Driver)
            .filter(
                Driver.id == user_data.driver_id
            )
            .first()
        )

        if driver is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="راننده پیدا نشد",
            )

        if not driver.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="راننده انتخاب‌شده فعال نیست",
            )

        if driver.university_id != user_data.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="راننده متعلق به دانشگاه انتخاب‌شده نیست",
            )

        existing_driver_user = (
            db.query(User)
            .filter(
                User.driver_id == driver.id
            )
            .first()
        )

        if existing_driver_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این راننده قبلاً دارای حساب کاربری است",
            )

    # =====================================================
    # سایر نقش‌ها
    # =====================================================

    else:

        if (
            user_data.student_id is not None
            or user_data.driver_id is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این نقش نباید به دانشجو یا راننده متصل باشد",
            )

    # =====================================================
    # ایجاد کاربر
    # =====================================================

    user = User(
        university_id=user_data.university_id,
        transport_company_id=user_data.transport_company_id,
        student_id=user_data.student_id,
        driver_id=user_data.driver_id,
        username=username,
        password_hash=hash_password(
            user_data.password
        ),
        first_name=(
            user_data.first_name.strip()
            if user_data.first_name
            else None
        ),
        last_name=(
            user_data.last_name.strip()
            if user_data.last_name
            else None
        ),
        phone=(
            user_data.phone.strip()
            if user_data.phone
            else None
        ),
        role=target_role,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


# =========================================================
# مشاهده کاربران
# =========================================================

@router.get(
    "/",
    response_model=list[UserProfileResponse],
)
def get_users(
    role: str | None = None,
    university_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده کاربران را ندارید",
        )

    query = db.query(User)

    if current_user.role == Roles.UNIVERSITY_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            User.university_id == current_user.university_id
        )

    elif university_id is not None:

        query = query.filter(
            User.university_id == university_id
        )

    if role is not None:

        if role not in ALL_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="نقش کاربر نامعتبر است",
            )

        query = query.filter(
            User.role == role
        )

    if is_active is not None:

        query = query.filter(
            User.is_active == is_active
        )

    return (
        query
        .order_by(
            User.id.desc()
        )
        .all()
    )


# =========================================================
# مشاهده پروفایل خود
# =========================================================

@router.get(
    "/me",
    response_model=UserProfileResponse,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


# =========================================================
# تغییر رمز شخصی
# =========================================================

@router.patch(
    "/me/password",
)
def change_my_password(
    password_data: ChangeMyPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(
        password_data.current_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز عبور فعلی اشتباه است",
        )

    if verify_password(
        password_data.new_password,
        current_user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز عبور جدید باید با رمز فعلی متفاوت باشد",
        )

    current_user.password_hash = hash_password(
        password_data.new_password,
    )

    db.commit()

    return {
        "message": "رمز عبور با موفقیت تغییر کرد",
    }


# =========================================================
# تغییر وضعیت کاربر
# =========================================================

@router.patch(
    "/{user_id}/status",
    response_model=UserStatusResponse,
)
def update_user_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت کاربران را ندارید",
        )

    user = get_user_or_404(
        db,
        user_id,
    )

    check_user_management_access(
        current_user,
        user,
    )

    if user.id == current_user.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نمی‌توانید حساب کاربری خودتان را غیرفعال کنید",
        )

    user.is_active = is_active

    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "message": "وضعیت کاربر با موفقیت تغییر کرد",
    }


# =========================================================
# تغییر رمز کاربر توسط مدیر
# =========================================================

@router.patch(
    "/{user_id}/password",
)
def change_user_password(
    user_id: int,
    password_data: ChangeUserPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر رمز کاربران را ندارید",
        )

    user = get_user_or_404(
        db,
        user_id,
    )

    check_user_management_access(
        current_user,
        user,
    )

    if verify_password(
        password_data.new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رمز عبور جدید باید با رمز قبلی متفاوت باشد",
        )

    user.password_hash = hash_password(
        password_data.new_password,
    )

    db.commit()

    return {
        "id": user.id,
        "username": user.username,
        "message": "رمز عبور با موفقیت تغییر کرد",
    }
