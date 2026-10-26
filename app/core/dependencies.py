from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.contract import Contract
from app.models.contract_driver import ContractDriver
from app.models.contract_vehicle import ContractVehicle
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.models.trip import Trip
from app.core.security import SECRET_KEY, ALGORITHM
from app.core.roles import Roles, ALL_ROLES


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# ============================================================
# Authentication
# ============================================================

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    دریافت کاربر جاری از روی JWT.

    اطلاعات حساس مانند role، university_id و
    transport_company_id از JWT اعتماد نمی‌شوند
    و مستقیماً از دیتابیس خوانده می‌شوند.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="احراز هویت نامعتبر است",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری غیرفعال است",
        )

    if user.role not in ALL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="نقش کاربری نامعتبر است",
        )

    return user


# ============================================================
# Role Access
# ============================================================

def require_roles(*allowed_roles):
    """
    محدود کردن دسترسی endpoint به نقش‌های مشخص.
    """

    invalid_roles = set(allowed_roles) - ALL_ROLES

    if invalid_roles:
        raise ValueError(
            f"نقش‌های نامعتبر در require_roles: {invalid_roles}"
        )

    if not allowed_roles:
        raise ValueError(
            "حداقل یک نقش باید در require_roles مشخص شود"
        )

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما مجوز دسترسی به این بخش را ندارید",
            )

        return current_user

    return role_checker


# ============================================================
# University Access
# ============================================================

def check_university_access(
    current_user: User,
    university_id: int,
) -> None:
    """
    کنترل دسترسی کاربر به یک دانشگاه.

    super_admin:
        دسترسی به همه دانشگاه‌ها

    کاربران دانشگاهی:
        فقط دانشگاه متصل به حساب خودشان

    company_admin:
        دسترسی مستقیم به دانشگاه ندارد و باید
        از مسیر قرارداد کنترل شود.
    """

    if university_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه دانشگاه نامعتبر است",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return

    if current_user.role == Roles.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="کاربر شرکت باید از طریق قرارداد به دانشگاه دسترسی داشته باشد",
        )

    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست",
        )

    if current_user.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به اطلاعات این دانشگاه دسترسی ندارید",
        )


def require_university_access(
    university_id: int,
):
    """
    Dependency برای endpointهایی که university_id
    به‌صورت ثابت در Dependency مشخص می‌شود.
    """

    def university_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        check_university_access(
            current_user=current_user,
            university_id=university_id,
        )

        return current_user

    return university_checker


# ============================================================
# Company Access - Basic
# ============================================================

def check_company_user(
    current_user: User,
) -> None:
    """
    اطمینان از اینکه کاربر یک مدیر شرکت معتبر است
    و به یک شرکت حمل‌ونقل متصل شده است.
    """

    if current_user.role != Roles.COMPANY_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این عملیات فقط برای مدیر شرکت مجاز است",
        )

    if current_user.transport_company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شرکت به شرکت حمل‌ونقلی متصل نیست",
        )


def check_company_id_access(
    current_user: User,
    transport_company_id: int,
) -> None:
    """
    بررسی دسترسی کاربر به یک شرکت حمل‌ونقل.

    super_admin:
        دسترسی به همه شرکت‌ها

    company_admin:
        فقط شرکت متصل به حساب خودش
    """

    if transport_company_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه شرکت حمل‌ونقل نامعتبر است",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return

    check_company_user(current_user)

    if current_user.transport_company_id != transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به این شرکت حمل‌ونقل دسترسی ندارید",
        )


# ============================================================
# Contract Access
# ============================================================

def get_contract(
    db: Session,
    contract_id: int,
) -> Contract:
    """
    دریافت قرارداد یا ایجاد خطای 404.
    """

    if contract_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه قرارداد نامعتبر است",
        )

    contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id)
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="قرارداد پیدا نشد",
        )

    return contract


def check_contract_access(
    current_user: User,
    contract: Contract,
) -> None:
    """
    کنترل دسترسی کاربر به یک قرارداد.

    super_admin:
        همه قراردادها

    کاربران دانشگاهی:
        قراردادهای دانشگاه خودشان

    company_admin:
        فقط قراردادهای شرکت خودشان و قرارداد فعال
    """

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="قرارداد پیدا نشد",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_user(current_user)

        if contract.transport_company_id != current_user.transport_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="این قرارداد متعلق به شرکت شما نیست",
            )

        if not contract.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="قرارداد غیرفعال است",
            )

        return

    check_university_access(
        current_user=current_user,
        university_id=contract.university_id,
    )


def check_company_contract_access(
    db: Session,
    current_user: User,
    contract_id: int,
) -> Contract:
    """
    کنترل کامل دسترسی کاربر به قرارداد.
    """

    contract = get_contract(
        db=db,
        contract_id=contract_id,
    )

    check_contract_access(
        current_user=current_user,
        contract=contract,
    )

    return contract


# ============================================================
# Driver Access
# ============================================================

def check_driver_company_access(
    db: Session,
    current_user: User,
    driver_id: int,
) -> Driver:
    """
    بررسی دسترسی شرکت به یک راننده.

    company_admin:

    1. راننده متعلق به همان شرکت باشد.
    2. راننده فعال باشد.
    3. راننده در حداقل یک قرارداد فعال شرکت
       مجاز به فعالیت باشد.
    """

    if driver_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه راننده نامعتبر است",
        )

    driver = (
        db.query(Driver)
        .filter(Driver.id == driver_id)
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="راننده پیدا نشد",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return driver

    check_company_user(current_user)

    if driver.transport_company_id != current_user.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این راننده متعلق به شرکت شما نیست",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="راننده غیرفعال است",
        )

    contract_exists = (
        db.query(ContractDriver.id)
        .join(
            Contract,
            Contract.id == ContractDriver.contract_id,
        )
        .filter(
            ContractDriver.driver_id == driver.id,
            ContractDriver.is_active.is_(True),
            Contract.transport_company_id
            == current_user.transport_company_id,
            Contract.is_active.is_(True),
        )
        .first()
    )

    if contract_exists is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این راننده در هیچ قرارداد فعال شرکت مجاز نیست",
        )

    return driver


def check_driver_contract_access(
    db: Session,
    current_user: User,
    contract_id: int,
    driver_id: int,
) -> ContractDriver:
    """
    بررسی می‌کند که راننده مشخص‌شده در قرارداد مشخص
    برای کاربر جاری قابل دسترسی باشد.
    """

    contract = check_company_contract_access(
        db=db,
        current_user=current_user,
        contract_id=contract_id,
    )

    assignment = (
        db.query(ContractDriver)
        .filter(
            ContractDriver.contract_id == contract.id,
            ContractDriver.driver_id == driver_id,
            ContractDriver.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این راننده برای قرارداد موردنظر مجاز نیست",
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        driver = (
            db.query(Driver)
            .filter(Driver.id == driver_id)
            .first()
        )

        if driver is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="راننده پیدا نشد",
            )

        if driver.transport_company_id != current_user.transport_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="این راننده متعلق به شرکت شما نیست",
            )

    return assignment


# ============================================================
# Vehicle Access
# ============================================================

def check_vehicle_company_access(
    db: Session,
    current_user: User,
    vehicle_id: int,
) -> Vehicle:
    """
    بررسی دسترسی شرکت به یک خودرو.

    company_admin:

    1. خودرو متعلق به همان شرکت باشد.
    2. خودرو فعال باشد.
    3. خودرو در حداقل یک قرارداد فعال شرکت
       مجاز به فعالیت باشد.
    """

    if vehicle_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه خودرو نامعتبر است",
        )

    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو پیدا نشد",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return vehicle

    check_company_user(current_user)

    if vehicle.transport_company_id != current_user.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این خودرو متعلق به شرکت شما نیست",
        )

    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="خودرو غیرفعال است",
        )

    contract_exists = (
        db.query(ContractVehicle.id)
        .join(
            Contract,
            Contract.id == ContractVehicle.contract_id,
        )
        .filter(
            ContractVehicle.vehicle_id == vehicle.id,
            ContractVehicle.is_active.is_(True),
            Contract.transport_company_id
            == current_user.transport_company_id,
            Contract.is_active.is_(True),
        )
        .first()
    )

    if contract_exists is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این خودرو در هیچ قرارداد فعال شرکت مجاز نیست",
        )

    return vehicle


def check_vehicle_contract_access(
    db: Session,
    current_user: User,
    contract_id: int,
    vehicle_id: int,
) -> ContractVehicle:
    """
    بررسی می‌کند که خودرو مشخص‌شده در قرارداد مشخص
    برای کاربر جاری قابل دسترسی باشد.
    """

    contract = check_company_contract_access(
        db=db,
        current_user=current_user,
        contract_id=contract_id,
    )

    assignment = (
        db.query(ContractVehicle)
        .filter(
            ContractVehicle.contract_id == contract.id,
            ContractVehicle.vehicle_id == vehicle_id,
            ContractVehicle.is_active.is_(True),
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این خودرو برای قرارداد موردنظر مجاز نیست",
        )

    if current_user.role == Roles.COMPANY_ADMIN:
        vehicle = (
            db.query(Vehicle)
            .filter(Vehicle.id == vehicle_id)
            .first()
        )

        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="خودرو پیدا نشد",
            )

        if vehicle.transport_company_id != current_user.transport_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="این خودرو متعلق به شرکت شما نیست",
            )

    return assignment


# ============================================================
# Trip Access
# ============================================================

def check_trip_company_access(
    db: Session,
    current_user: User,
    trip_id: int,
) -> Trip:
    """
    کنترل دسترسی شرکت حمل‌ونقل به یک سفر.

    مسیر مالکیت:

        Trip
          ↓
        Service
          ↓
        Contract
          ↓
        TransportCompany

    company_admin فقط زمانی به سفر دسترسی دارد که:

    1. سفر وجود داشته باشد.
    2. سرویس سفر وجود داشته باشد.
    3. سرویس به قرارداد متصل باشد.
    4. سرویس فعال باشد.
    5. قرارداد فعال باشد.
    6. قرارداد متعلق به شرکت کاربر باشد.
    7. دانشگاه قرارداد با دانشگاه سفر یکسان باشد.
    8. دانشگاه سرویس با دانشگاه سفر یکسان باشد.
    """

    if trip_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه سفر نامعتبر است",
        )

    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر پیدا نشد",
        )

    if current_user.role == Roles.SUPER_ADMIN:
        return trip

    if current_user.role != Roles.COMPANY_ADMIN:
        check_university_access(
            current_user=current_user,
            university_id=trip.university_id,
        )
        return trip

    check_company_user(current_user)

    service = trip.service

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="سرویس این سفر پیدا نشد",
        )

    if not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="سرویس این سفر غیرفعال است",
        )

    if service.contract_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر تحت قرارداد شرکت حمل‌ونقل قرار ندارد",
        )

    contract = service.contract

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="قرارداد سرویس این سفر پیدا نشد",
        )

    if not contract.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="قرارداد مربوط به این سفر غیرفعال است",
        )

    if contract.transport_company_id != current_user.transport_company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر تحت قرارداد شرکت شما نیست",
        )

    if contract.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه قرارداد با دانشگاه سفر مطابقت ندارد",
        )

    if service.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دانشگاه سرویس با دانشگاه سفر مطابقت ندارد",
        )

    return trip