from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vehicle import Vehicle
from app.models.driver import Driver
from app.models.user import User
from app.models.university import University
from app.models.contract import Contract
from app.models.contract_vehicle import ContractVehicle
from app.schemas.vehicle import VehicleCreate, VehicleResponse
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_vehicle_company_access,
)
from app.core.roles import Roles


router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicles"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}

VIEW_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
}


def normalize_text(value: str | None):
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


def validate_driver(
    db: Session,
    driver_id: int | None,
    university_id: int,
    transport_company_id: int | None = None,
):
    if driver_id is None:
        return None

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

    if driver.university_id != university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده متعلق به این دانشگاه نیست",
        )

    if not driver.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="راننده انتخاب‌شده غیرفعال است",
        )

    if transport_company_id is not None:
        if driver.transport_company_id != transport_company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="راننده متعلق به شرکت شما نیست",
            )

    return driver


def get_vehicle_or_404(
    db: Session,
    vehicle_id: int,
):
    if vehicle_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه خودرو نامعتبر است",
        )

    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id
        )
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو پیدا نشد",
        )

    return vehicle


def check_vehicle_access(
    db: Session,
    current_user: User,
    vehicle: Vehicle,
):
    """
    کنترل دسترسی به خودرو:

    - super_admin: دسترسی کامل
    - company_admin: فقط خودروهای شرکت خودش
    - سایر مدیران: فقط خودروهای دانشگاه خودشان
    """

    if current_user.role == Roles.COMPANY_ADMIN:
        check_vehicle_company_access(
            db,
            current_user,
            vehicle.id,
        )
        return

    check_university_access(
        current_user,
        vehicle.university_id,
    )


# =========================================================
# ایجاد خودرو
# =========================================================

@router.post(
    "/",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vehicle(
    vehicle_data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ایجاد خودرو را ندارید",
        )

    check_university_access(
        current_user,
        vehicle_data.university_id,
    )

    get_active_university(
        db,
        vehicle_data.university_id,
    )

    plate_number = normalize_text(
        vehicle_data.plate_number
    )

    vehicle_type = normalize_text(
        vehicle_data.vehicle_type
    )

    if not plate_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره پلاک نمی‌تواند خالی باشد",
        )

    if not vehicle_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع خودرو نمی‌تواند خالی باشد",
        )

    existing_vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.plate_number == plate_number
        )
        .first()
    )

    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این پلاک قبلاً ثبت شده است",
        )

    driver = validate_driver(
        db,
        vehicle_data.driver_id,
        vehicle_data.university_id,
    )

    transport_company_id = None

    if driver is not None:
        transport_company_id = driver.transport_company_id

    vehicle = Vehicle(
        university_id=vehicle_data.university_id,
        transport_company_id=transport_company_id,
        driver_id=vehicle_data.driver_id,
        plate_number=plate_number,
        vehicle_type=vehicle_type,
        capacity=vehicle_data.capacity,
        is_active=vehicle_data.is_active,
    )

    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)

    return vehicle


# =========================================================
# فهرست خودروها
# =========================================================

@router.get(
    "/",
    response_model=list[VehicleResponse],
)
def get_vehicles(
    university_id: int | None = None,
    driver_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده خودروها را ندارید",
        )

    query = db.query(Vehicle)

    if current_user.role == Roles.COMPANY_ADMIN:

        if current_user.transport_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شرکت به شرکت حمل‌ونقلی متصل نیست",
            )

        query = (
            query
            .join(
                ContractVehicle,
                ContractVehicle.vehicle_id == Vehicle.id,
            )
            .join(
                Contract,
                Contract.id == ContractVehicle.contract_id,
            )
            .filter(
                Vehicle.transport_company_id
                == current_user.transport_company_id,
                Vehicle.is_active.is_(True),
                ContractVehicle.is_active.is_(True),
                Contract.transport_company_id
                == current_user.transport_company_id,
                Contract.is_active.is_(True),
            )
            .distinct()
        )

        if university_id is not None:
            query = query.filter(
                Vehicle.university_id == university_id
            )

        if driver_id is not None:
            query = query.filter(
                Vehicle.driver_id == driver_id
            )

        if is_active is not None:
            query = query.filter(
                Vehicle.is_active == is_active
            )

        return (
            query
            .order_by(Vehicle.id.desc())
            .all()
        )

    if current_user.role != Roles.SUPER_ADMIN:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Vehicle.university_id == current_user.university_id
        )

    elif university_id is not None:

        query = query.filter(
            Vehicle.university_id == university_id
        )

    if driver_id is not None:
        query = query.filter(
            Vehicle.driver_id == driver_id
        )

    if is_active is not None:
        query = query.filter(
            Vehicle.is_active == is_active
        )

    return (
        query
        .order_by(Vehicle.id.desc())
        .all()
    )


# =========================================================
# مشاهده یک خودرو
# =========================================================

@router.get(
    "/{vehicle_id}",
    response_model=VehicleResponse,
)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده این خودرو را ندارید",
        )

    vehicle = get_vehicle_or_404(
        db,
        vehicle_id,
    )

    check_vehicle_access(
        db,
        current_user,
        vehicle,
    )

    return vehicle


# =========================================================
# ویرایش خودرو
# =========================================================

@router.patch(
    "/{vehicle_id}",
    response_model=VehicleResponse,
)
def update_vehicle(
    vehicle_id: int,
    vehicle_data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ویرایش خودرو را ندارید",
        )

    vehicle = get_vehicle_or_404(
        db,
        vehicle_id,
    )

    check_vehicle_access(
        db,
        current_user,
        vehicle,
    )

    if current_user.role == Roles.COMPANY_ADMIN:

        if vehicle_data.university_id != vehicle.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="شرکت حمل‌ونقل مجاز به تغییر دانشگاه خودرو نیست",
            )

        if vehicle_data.is_active != vehicle.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شرکت حمل‌ونقل مجاز به تغییر وضعیت خودرو نیست",
            )

        driver = validate_driver(
            db,
            vehicle_data.driver_id,
            vehicle.university_id,
            current_user.transport_company_id,
        )

    else:

        if vehicle_data.university_id != vehicle.university_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="امکان تغییر دانشگاه خودرو از این بخش وجود ندارد",
            )

        get_active_university(
            db,
            vehicle.university_id,
        )

        driver = validate_driver(
            db,
            vehicle_data.driver_id,
            vehicle.university_id,
        )

    plate_number = normalize_text(
        vehicle_data.plate_number
    )

    vehicle_type = normalize_text(
        vehicle_data.vehicle_type
    )

    if not plate_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شماره پلاک نمی‌تواند خالی باشد",
        )

    if not vehicle_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نوع خودرو نمی‌تواند خالی باشد",
        )

    existing_vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.plate_number == plate_number,
            Vehicle.id != vehicle.id,
        )
        .first()
    )

    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این پلاک قبلاً ثبت شده است",
        )

    vehicle.driver_id = vehicle_data.driver_id

    if driver is not None:
        vehicle.transport_company_id = driver.transport_company_id
    else:
        vehicle.transport_company_id = None

    vehicle.plate_number = plate_number
    vehicle.vehicle_type = vehicle_type
    vehicle.capacity = vehicle_data.capacity

    if current_user.role in MANAGEMENT_ROLES:
        vehicle.is_active = vehicle_data.is_active

    db.commit()
    db.refresh(vehicle)

    return vehicle


# =========================================================
# تغییر وضعیت خودرو
# =========================================================

@router.patch(
    "/{vehicle_id}/status",
    response_model=VehicleResponse,
)
def update_vehicle_status(
    vehicle_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز تغییر وضعیت خودرو را ندارید",
        )

    vehicle = get_vehicle_or_404(
        db,
        vehicle_id,
    )

    check_university_access(
        current_user,
        vehicle.university_id,
    )

    vehicle.is_active = is_active

    db.commit()
    db.refresh(vehicle)

    return vehicle