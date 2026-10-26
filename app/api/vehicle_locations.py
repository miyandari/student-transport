from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vehicle_location import VehicleLocation
from app.models.trip import Trip
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.vehicle_location import (
    VehicleLocationCreate,
    VehicleLocationResponse,
)
from app.core.dependencies import (
    get_current_user,
    check_university_access,
    check_vehicle_company_access,
    check_trip_company_access,
    check_company_user,
)
from app.core.roles import (
    Roles,
    MANAGEMENT_ROLES,
)
from app.services.vehicle_location_service import (
    create_vehicle_location,
    get_vehicle_locations,
    get_latest_vehicle_location,
    get_trip,
    get_vehicle,
    validate_driver_vehicle_access,
)


router = APIRouter(
    prefix="/vehicle-locations",
    tags=["Vehicle Locations"],
)


WRITE_ROLES = MANAGEMENT_ROLES | {
    Roles.COMPANY_ADMIN,
    Roles.DRIVER,
}

VIEW_ROLES = WRITE_ROLES | {
    Roles.STUDENT,
}


def check_trip_access(
    db: Session,
    current_user: User,
    trip: Trip,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:
        check_trip_company_access(
            db,
            current_user,
            trip,
        )
        return

    check_university_access(
        current_user,
        trip.university_id,
    )


def check_vehicle_access(
    db: Session,
    current_user: User,
    vehicle: Vehicle,
) -> None:

    if current_user.role == Roles.COMPANY_ADMIN:
        check_vehicle_company_access(
            db,
            current_user,
            vehicle,
        )
        return

    check_university_access(
        current_user,
        vehicle.university_id,
    )


def check_driver_trip_access(
    current_user: User,
    trip: Trip,
    vehicle: Vehicle,
) -> None:

    if current_user.role != Roles.DRIVER:
        return

    if current_user.driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری راننده به یک راننده متصل نیست",
        )

    validate_driver_vehicle_access(
        current_user.driver_id,
        trip,
        vehicle,
    )


def check_company_location_access(
    db: Session,
    current_user: User,
    location: VehicleLocation,
) -> None:

    if current_user.role != Roles.COMPANY_ADMIN:
        return

    trip = get_trip(
        db,
        location.trip_id,
    )

    vehicle = get_vehicle(
        db,
        location.vehicle_id,
    )

    check_trip_company_access(
        db,
        current_user,
        trip,
    )

    check_vehicle_company_access(
        db,
        current_user,
        vehicle,
    )


@router.post(
    "/",
    response_model=VehicleLocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vehicle_location_endpoint(
    location_data: VehicleLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز ثبت موقعیت خودرو را ندارید",
        )

    trip = get_trip(
        db,
        location_data.trip_id,
    )

    vehicle = get_vehicle(
        db,
        location_data.vehicle_id,
    )

    # ---------------------------------------------------------
    # Company Admin
    # ---------------------------------------------------------
    if current_user.role == Roles.COMPANY_ADMIN:

        check_company_user(current_user)

        check_trip_company_access(
            db,
            current_user,
            trip,
        )

        check_vehicle_company_access(
            db,
            current_user,
            vehicle,
        )

        if trip.vehicle_id != vehicle.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="خودروی انتخاب‌شده برای این سفر تعیین نشده است",
            )

    # ---------------------------------------------------------
    # Driver
    # ---------------------------------------------------------
    elif current_user.role == Roles.DRIVER:

        check_university_access(
            current_user,
            trip.university_id,
        )

        check_university_access(
            current_user,
            vehicle.university_id,
        )

        check_driver_trip_access(
            current_user,
            trip,
            vehicle,
        )

    # ---------------------------------------------------------
    # University Management / Super Admin
    # ---------------------------------------------------------
    else:

        check_university_access(
            current_user,
            trip.university_id,
        )

        check_university_access(
            current_user,
            vehicle.university_id,
        )

    if trip.university_id != vehicle.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سفر و خودرو متعلق به یک دانشگاه نیستند",
        )

    location = await create_vehicle_location(
        db,
        trip_id=location_data.trip_id,
        vehicle_id=location_data.vehicle_id,
        latitude=location_data.latitude,
        longitude=location_data.longitude,
        speed=location_data.speed,
        heading=location_data.heading,
        recorded_at=location_data.recorded_at,
    )

    return location


@router.get(
    "/",
    response_model=list[VehicleLocationResponse],
)
def get_vehicle_locations_endpoint(
    trip_id: int | None = Query(default=None),
    vehicle_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده موقعیت خودرو را ندارید",
        )

    # ---------------------------------------------------------
    # بررسی دسترسی Trip
    # ---------------------------------------------------------
    trip = None

    if trip_id is not None:

        trip = get_trip(
            db,
            trip_id,
        )

        check_trip_access(
            db,
            current_user,
            trip,
        )

        if current_user.role == Roles.DRIVER:

            if trip.vehicle_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="برای این سفر خودرویی تعیین نشده است",
                )

            vehicle = get_vehicle(
                db,
                trip.vehicle_id,
            )

            check_driver_trip_access(
                current_user,
                trip,
                vehicle,
            )

    # ---------------------------------------------------------
    # بررسی دسترسی Vehicle
    # ---------------------------------------------------------
    vehicle = None

    if vehicle_id is not None:

        vehicle = get_vehicle(
            db,
            vehicle_id,
        )

        check_vehicle_access(
            db,
            current_user,
            vehicle,
        )

        if current_user.role == Roles.DRIVER:

            if current_user.driver_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="حساب کاربری راننده به یک راننده متصل نیست",
                )

            if vehicle.driver_id != current_user.driver_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="شما به موقعیت این خودرو دسترسی ندارید",
                )

    # ---------------------------------------------------------
    # جلوگیری از دریافت کلی اطلاعات توسط کاربران عادی
    # ---------------------------------------------------------
    if (
        trip_id is None
        and vehicle_id is None
        and current_user.role not in {
            Roles.SUPER_ADMIN,
            Roles.COMPANY_ADMIN,
        }
    ):

        if current_user.university_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="حساب کاربری شما به دانشگاهی متصل نیست",
            )

    locations = get_vehicle_locations(
        db,
        trip_id=trip_id,
        vehicle_id=vehicle_id,
    )

    # ---------------------------------------------------------
    # Super Admin
    # ---------------------------------------------------------
    if current_user.role == Roles.SUPER_ADMIN:
        return locations

    # ---------------------------------------------------------
    # Company Admin
    # ---------------------------------------------------------
    if current_user.role == Roles.COMPANY_ADMIN:

        authorized_locations = []

        for location in locations:

            try:
                check_company_location_access(
                    db,
                    current_user,
                    location,
                )
                authorized_locations.append(location)

            except HTTPException:
                continue

        return authorized_locations

    # ---------------------------------------------------------
    # سایر کاربران
    # ---------------------------------------------------------
    if current_user.university_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری شما به دانشگاهی متصل نیست",
        )

    university_id = current_user.university_id

    return [
        location
        for location in locations
        if location.trip.university_id == university_id
    ]


@router.get(
    "/latest/{trip_id}",
    response_model=VehicleLocationResponse,
)
def get_latest_vehicle_location_endpoint(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if current_user.role not in VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده موقعیت خودرو را ندارید",
        )

    trip = get_trip(
        db,
        trip_id,
    )

    # ---------------------------------------------------------
    # Company Admin
    # ---------------------------------------------------------
    if current_user.role == Roles.COMPANY_ADMIN:

        check_trip_company_access(
            db,
            current_user,
            trip,
        )

    # ---------------------------------------------------------
    # سایر کاربران
    # ---------------------------------------------------------
    else:

        check_university_access(
            current_user,
            trip.university_id,
        )

    if current_user.role == Roles.DRIVER:

        if trip.vehicle_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="برای این سفر خودرویی تعیین نشده است",
            )

        vehicle = get_vehicle(
            db,
            trip.vehicle_id,
        )

        check_driver_trip_access(
            current_user,
            trip,
            vehicle,
        )

    location = get_latest_vehicle_location(
        db,
        trip_id=trip_id,
    )

    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="موقعیت ثبت‌شده‌ای برای این سفر پیدا نشد",
        )

    # در حالت company_admin، خود Vehicle نیز کنترل می‌شود.
    if current_user.role == Roles.COMPANY_ADMIN:

        vehicle = get_vehicle(
            db,
            location.vehicle_id,
        )

        check_vehicle_company_access(
            db,
            current_user,
            vehicle,
        )

    return location