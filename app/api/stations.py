from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.station import Station
from app.models.university import University
from app.models.contract import Contract
from app.models.user import User
from app.schemas.station import (
    StationCreate,
    StationResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_company_user,
)
from app.core.roles import Roles


router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)


MANAGEMENT_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
}


VIEW_ROLES = {
    Roles.SUPER_ADMIN,
    Roles.UNIVERSITY_ADMIN,
    Roles.TRANSPORT_MANAGER,
    Roles.COMPANY_ADMIN,
    Roles.DRIVER,
    Roles.STUDENT,
}


def normalize_text(
    value: str | None,
):
    if value is None:
        return None

    return value.strip()


def check_management_role(
    current_user: User,
) -> None:

    if current_user.role not in MANAGEMENT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مدیریت ایستگاه‌ها را ندارید",
        )


def check_view_role(
    current_user: User,
) -> None:

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده ایستگاه‌ها را ندارید",
        )


def check_company_university_access(
    db: Session,
    current_user: User,
    university_id: int,
) -> Contract:

    check_company_user(current_user)

    contract = (
        db.query(Contract)
        .filter(
            Contract.transport_company_id
            == current_user.transport_company_id,
            Contract.university_id == university_id,
            Contract.is_active.is_(True),
        )
        .first()
    )

    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شرکت شما با این دانشگاه قرارداد فعال ندارد",
        )

    return contract


def check_university_access(
    current_user: User,
    university_id: int,
) -> None:

    if current_user.role == Roles.SUPER_ADMIN:
        return

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


def check_station_view_access(
    db: Session,
    current_user: User,
    university_id: int,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:
        check_company_university_access(
            db,
            current_user,
            university_id,
        )
        return

    check_university_access(
        current_user,
        university_id,
    )


def validate_university(
    db: Session,
    university_id: int,
) -> University:

    university = (
        db.query(University)
        .filter(
            University.id == university_id,
        )
        .first()
    )

    if university is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشگاه موردنظر پیدا نشد",
        )

    if not university.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشگاه موردنظر غیرفعال است",
        )

    return university


def validate_station_data(
    db: Session,
    station_data: StationCreate,
    current_station_id: int | None = None,
) -> tuple[str, str | None]:

    name = normalize_text(
        station_data.name,
    )

    address = normalize_text(
        station_data.address,
    )

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="نام ایستگاه نمی‌تواند خالی باشد",
        )

    if (
        (station_data.latitude is None)
        != (station_data.longitude is None)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="عرض و طول جغرافیایی باید هر دو وارد شوند",
        )

    query = (
        db.query(Station)
        .filter(
            Station.university_id
            == station_data.university_id,
            Station.name == name,
        )
    )

    if current_station_id is not None:
        query = query.filter(
            Station.id != current_station_id,
        )

    existing_station = query.first()

    if existing_station:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ایستگاهی با این نام قبلاً در این دانشگاه ثبت شده است",
        )

    return name, address


# =========================================================
# Create Station
# =========================================================

@router.post(
    "/",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_station(
    station_data: StationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(
        current_user,
    )

    validate_university(
        db,
        station_data.university_id,
    )

    check_university_access(
        current_user,
        station_data.university_id,
    )

    name, address = validate_station_data(
        db,
        station_data,
    )

    station = Station(
        university_id=station_data.university_id,
        name=name,
        address=address,
        latitude=station_data.latitude,
        longitude=station_data.longitude,
        is_active=station_data.is_active,
    )

    db.add(station)

    try:
        db.commit()
        db.refresh(station)
    except Exception:
        db.rollback()
        raise

    return station


# =========================================================
# Get Stations
# =========================================================

@router.get(
    "/",
    response_model=list[StationResponse],
)
def get_stations(
    university_id: int | None = None,
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user,
    )

    query = db.query(Station)

    # -----------------------------------------------------
    # Super Admin
    # -----------------------------------------------------

    if current_user.role == Roles.SUPER_ADMIN:

        if university_id is not None:
            query = query.filter(
                Station.university_id == university_id,
            )

    # -----------------------------------------------------
    # Company Admin
    # -----------------------------------------------------

    elif current_user.role == Roles.COMPANY_ADMIN:

        check_company_user(
            current_user,
        )

        query = (
            query
            .join(
                Contract,
                Contract.university_id
                == Station.university_id,
            )
            .filter(
                Contract.transport_company_id
                == current_user.transport_company_id,
                Contract.is_active.is_(True),
            )
        )

        if university_id is not None:

            check_company_university_access(
                db,
                current_user,
                university_id,
            )

            query = query.filter(
                Station.university_id == university_id,
            )

    # -----------------------------------------------------
    # University Users / Driver / Student
    # -----------------------------------------------------

    else:

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

        query = query.filter(
            Station.university_id
            == current_user.university_id,
        )

    if is_active is not None:
        query = query.filter(
            Station.is_active == is_active,
        )

    return (
        query
        .distinct()
        .order_by(
            Station.id.desc(),
        )
        .all()
    )


# =========================================================
# Get Station QR Information
# =========================================================

@router.get(
    "/{station_id}/qr",
)
def get_station_qr(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    check_view_role(
        current_user,
    )

    if station_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه ایستگاه نامعتبر است",
        )

    station = (
        db.query(Station)
        .filter(
            Station.id == station_id,
            Station.is_active.is_(True),
        )
        .first()
    )

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه موردنظر پیدا نشد یا غیرفعال است",
        )

    check_station_view_access(
        db,
        current_user,
        station.university_id,
    )

    return {
        "station_id": station.id,
        "station_name": station.name,
        "university_id": station.university_id,
        "qr_type": "station_boarding",
        "qr_data": f"station:{station.id}",
    }


# =========================================================
# Get Station By ID
# =========================================================

@router.get(
    "/{station_id}",
    response_model=StationResponse,
)
def get_station(
    station_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_view_role(
        current_user,
    )

    if station_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه ایستگاه نامعتبر است",
        )

    station = (
        db.query(Station)
        .filter(
            Station.id == station_id,
        )
        .first()
    )

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه موردنظر پیدا نشد",
        )

    check_station_view_access(
        db,
        current_user,
        station.university_id,
    )

    return station


# =========================================================
# Update Station
# =========================================================

@router.patch(
    "/{station_id}",
    response_model=StationResponse,
)
def update_station(
    station_id: int,
    station_data: StationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    check_management_role(
        current_user,
    )

    if station_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="شناسه ایستگاه نامعتبر است",
        )

    station = (
        db.query(Station)
        .filter(
            Station.id == station_id,
        )
        .first()
    )

    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ایستگاه موردنظر پیدا نشد",
        )

    check_university_access(
        current_user,
        station.university_id,
    )

    if (
        station_data.university_id
        != station.university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="امکان تغییر دانشگاه ایستگاه وجود ندارد",
        )

    name, address = validate_station_data(
        db,
        station_data,
        current_station_id=station.id,
    )

    station.name = name
    station.address = address
    station.latitude = station_data.latitude
    station.longitude = station_data.longitude
    station.is_active = station_data.is_active

    try:
        db.commit()
        db.refresh(station)
    except Exception:
        db.rollback()
        raise

    return station