
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.driver import Driver
from app.models.user import User
from app.models.university import University
from app.models.transport_company import TransportCompany

from app.schemas.driver import (
    DriverCreate,
    DriverResponse,
)

from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_driver_company_access,
)

from app.core.roles import Roles


router = APIRouter(
    prefix="/drivers",
    tags=["Drivers"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}


VIEW_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


def check_driver_access(
    db: Session,
    current_user: User,
    driver: Driver,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:

        check_driver_company_access(
            db,
            current_user,
            driver,
        )

        return

    check_university_access(
        current_user=current_user,
        university_id=driver.university_id,
    )


def normalize_text(
    value: str | None,
):
    if value is None:
        return None

    value = value.strip()

    return value if value else None


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


def get_driver_or_404(
    db: Session,
    driver_id: int,
) -> Driver:

    driver = (
        db.query(Driver)
        .filter(
            Driver.id == driver_id
        )
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده پیدا نشد",
        )

    return driver


def validate_driver_data(
    db: Session,
    driver_data: DriverCreate,
    current_driver_id: int | None = None,
) -> dict:

    first_name = normalize_text(
        driver_data.first_name
    )

    last_name = normalize_text(
        driver_data.last_name
    )

    national_id = normalize_text(
        driver_data.national_id
    )

    phone = normalize_text(
        driver_data.phone
    )

    license_number = normalize_text(
        driver_data.license_number
    )

    if not first_name or not last_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام و نام خانوادگی نمی‌توانند خالی باشند",
        )

    if not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره تلفن نمی‌تواند خالی باشد",
        )

    # -----------------------------------------------------
    # License number uniqueness
    # -----------------------------------------------------

    if license_number:

        query = (
            db.query(Driver)
            .filter(
                Driver.license_number == license_number
            )
        )

        if current_driver_id is not None:
            query = query.filter(
                Driver.id != current_driver_id
            )

        existing_license = query.first()

        if existing_license:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این شماره گواهینامه قبلاً ثبت شده است",
            )

    # -----------------------------------------------------
    # National ID uniqueness
    # -----------------------------------------------------

    if national_id:

        query = (
            db.query(Driver)
            .filter(
                Driver.national_id == national_id
            )
        )

        if current_driver_id is not None:
            query = query.filter(
                Driver.id != current_driver_id
            )

        existing_national_id = query.first()

        if existing_national_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="این کد ملی قبلاً ثبت شده است",
            )

    return {
        "first_name": first_name,
        "last_name": last_name,
        "national_id": national_id,
        "phone": phone,
        "license_number": license_number,
    }


# =========================================================
# Create Driver
# University Management Only
# =========================================================

@router.post(
    "/",
    response_model=DriverResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_driver(
    driver_data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد راننده را ندارید",
        )

    check_university_access(
        current_user=current_user,
        university_id=driver_data.university_id,
    )

    get_active_university(
        db,
        driver_data.university_id,
    )

    # -----------------------------------------------------
    # Transport company validation
    # -----------------------------------------------------

    if driver_data.transport_company_id is not None:

        get_active_transport_company(
            db,
            driver_data.transport_company_id,
        )

    validated_data = validate_driver_data(
        db,
        driver_data,
    )

    driver = Driver(
        university_id=driver_data.university_id,
        transport_company_id=driver_data.transport_company_id,
        first_name=validated_data["first_name"],
        last_name=validated_data["last_name"],
        national_id=validated_data["national_id"],
        phone=validated_data["phone"],
        license_number=validated_data["license_number"],
        is_active=driver_data.is_active,
    )

    db.add(driver)
    db.commit()
    db.refresh(driver)

    return driver


# =========================================================
# List Drivers
# =========================================================

@router.get(
    "/",
    response_model=list[DriverResponse],
)
def get_drivers(
    university_id: int | None = None,
    transport_company_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده رانندگان را ندارید",
        )

    # -----------------------------------------------------
    # Company access
    # -----------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب شرکت به شرکت حمل‌ونقل متصل نیست",
            )

        if (
            transport_company_id is not None
            and transport_company_id
            != current_user.transport_company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما فقط به رانندگان شرکت خود دسترسی دارید",
            )

        query = (
            db.query(Driver)
            .filter(
                Driver.transport_company_id
                == current_user.transport_company_id
            )
        )

        if university_id is not None:
            query = query.filter(
                Driver.university_id == university_id
            )

        if is_active is not None:
            query = query.filter(
                Driver.is_active == is_active
            )

        return (
            query
            .order_by(
                Driver.id.desc()
            )
            .all()
        )

    # -----------------------------------------------------
    # University management
    # -----------------------------------------------------

    query = db.query(Driver)

    if current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Driver.university_id == current_user.university_id
        )

    elif university_id is not None:

        query = query.filter(
            Driver.university_id == university_id
        )

    if transport_company_id is not None:

        query = query.filter(
            Driver.transport_company_id == transport_company_id
        )

    if is_active is not None:

        query = query.filter(
            Driver.is_active == is_active
        )

    return (
        query
        .order_by(
            Driver.id.desc()
        )
        .all()
    )


# =========================================================
# Get Driver
# =========================================================

@router.get(
    "/{driver_id}",
    response_model=DriverResponse,
)
def get_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این راننده را ندارید",
        )

    driver = get_driver_or_404(
        db,
        driver_id,
    )

    check_driver_access(
        db,
        current_user,
        driver,
    )

    return driver


# =========================================================
# Update Driver
# University Management / Company
# =========================================================

@router.patch(
    "/{driver_id}",
    response_model=DriverResponse,
)
def update_driver(
    driver_id: int,
    driver_data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if (
        current_user.role not in MANAGEMENT_ROLES
        and current_user.role != Roles.COMPANY_ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش راننده را ندارید",
        )

    driver = get_driver_or_404(
        db,
        driver_id,
    )

    check_driver_access(
        db,
        current_user,
        driver,
    )

    # -----------------------------------------------------
    # University cannot be changed from this endpoint
    # -----------------------------------------------------

    if driver_data.university_id != driver.university_id:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه راننده از این بخش وجود ندارد",
        )

    get_active_university(
        db,
        driver.university_id,
    )

    # -----------------------------------------------------
    # Company access
    # -----------------------------------------------------

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب شرکت به شرکت حمل‌ونقل متصل نیست",
            )

        if (
            driver_data.transport_company_id is not None
            and driver_data.transport_company_id
            != current_user.transport_company_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="امکان انتقال راننده به شرکت دیگر وجود ندارد",
            )

        # Company cannot change company ownership.
        transport_company_id = driver.transport_company_id

    else:

        # -------------------------------------------------
        # University management
        # -------------------------------------------------

        if driver_data.transport_company_id is not None:

            get_active_transport_company(
                db,
                driver_data.transport_company_id,
            )

        transport_company_id = driver_data.transport_company_id

    validated_data = validate_driver_data(
        db,
        driver_data,
        current_driver_id=driver.id,
    )

    driver.first_name = validated_data["first_name"]
    driver.last_name = validated_data["last_name"]
    driver.national_id = validated_data["national_id"]
    driver.phone = validated_data["phone"]
    driver.license_number = validated_data["license_number"]

    # -----------------------------------------------------
    # Update company
    # -----------------------------------------------------

    driver.transport_company_id = transport_company_id

    # -----------------------------------------------------
    # Company must not activate/deactivate independently
    # -----------------------------------------------------

    if current_user.role in MANAGEMENT_ROLES:

        driver.is_active = driver_data.is_active

    db.commit()
    db.refresh(driver)

    return driver


# =========================================================
# Change Driver Status
# University Management Only
# =========================================================

@router.patch(
    "/{driver_id}/status",
    response_model=DriverResponse,
)
def update_driver_status(
    driver_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت راننده را ندارید",
        )

    driver = get_driver_or_404(
        db,
        driver_id,
    )

    check_university_access(
        current_user=current_user,
        university_id=driver.university_id,
    )

    driver.is_active = is_active

    db.commit()
    db.refresh(driver)

    return driver
