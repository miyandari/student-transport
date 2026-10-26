from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.vehicle_location import VehicleLocation
from app.models.trip import Trip
from app.models.vehicle import Vehicle
from app.realtime.connection_manager import connection_manager
from app.services.eta_service import get_next_station
from app.services.station_event_service import detect_station_event
from app.services.trip_lifecycle_service import (
    complete_trip_if_arrived_at_final_station,
)


ACTIVE_LOCATION_TRIP_STATUSES = {
    "boarding",
    "in_progress",
}


def get_trip(
    db: Session,
    trip_id: int,
) -> Trip:
    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id,
        )
        .first()
    )

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    return trip


def get_vehicle(
    db: Session,
    vehicle_id: int,
) -> Vehicle:
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == vehicle_id,
        )
        .first()
    )

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="خودرو پیدا نشد",
        )

    return vehicle


def get_vehicle_locations(
    db: Session,
    *,
    trip_id: int | None = None,
    vehicle_id: int | None = None,
) -> list[VehicleLocation]:
    query = db.query(VehicleLocation)

    if trip_id is not None:
        query = query.filter(
            VehicleLocation.trip_id == trip_id,
        )

    if vehicle_id is not None:
        query = query.filter(
            VehicleLocation.vehicle_id == vehicle_id,
        )

    return (
        query
        .order_by(
            VehicleLocation.recorded_at.asc(),
            VehicleLocation.id.asc(),
        )
        .all()
    )


def get_latest_vehicle_location(
    db: Session,
    *,
    trip_id: int,
) -> VehicleLocation:
    location = (
        db.query(VehicleLocation)
        .filter(
            VehicleLocation.trip_id == trip_id,
        )
        .order_by(
            VehicleLocation.recorded_at.desc(),
            VehicleLocation.id.desc(),
        )
        .first()
    )

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="برای این سفر هنوز موقعیت GPS ثبت نشده است",
        )

    return location


def validate_trip_for_location(
    trip: Trip,
) -> None:
    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )

    if trip.status not in ACTIVE_LOCATION_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="در وضعیت فعلی سفر امکان ثبت موقعیت وجود ندارد",
        )


def validate_vehicle_for_trip(
    vehicle: Vehicle,
    trip: Trip,
) -> None:
    if not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خودروی انتخاب‌شده غیرفعال است",
        )

    if vehicle.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سفر و خودرو متعلق به یک دانشگاه نیستند",
        )

    if trip.vehicle_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سفر خودرویی تعیین نشده است",
        )

    if trip.vehicle_id != vehicle.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این خودرو برای سفر انتخاب نشده است",
        )


def validate_driver_vehicle_access(
    driver_id: int | None,
    trip: Trip,
    vehicle: Vehicle,
) -> None:
    if driver_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="حساب کاربری راننده به یک راننده متصل نیست",
        )

    if trip.driver_id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سفر به شما اختصاص داده نشده است",
        )

    if vehicle.driver_id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این خودرو به شما اختصاص داده نشده است",
        )


def validate_recorded_at(
    recorded_at: datetime,
) -> None:
    if (
        recorded_at.tzinfo is None
        or recorded_at.utcoffset() is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان ثبت موقعیت باید دارای منطقه زمانی باشد",
        )

    now = datetime.now(timezone.utc)

    if recorded_at.astimezone(timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="زمان ثبت موقعیت نمی‌تواند در آینده باشد",
        )


async def create_vehicle_location(
    db: Session,
    *,
    trip_id: int,
    vehicle_id: int,
    latitude: float,
    longitude: float,
    speed: float | None,
    heading: float | None,
    recorded_at: datetime,
    driver_id: int | None = None,
):
    # ---------------------------------------------------------
    # 1. دریافت و اعتبارسنجی سفر
    # ---------------------------------------------------------

    trip = get_trip(
        db,
        trip_id=trip_id,
    )

    validate_trip_for_location(trip)

    # ---------------------------------------------------------
    # 2. دریافت و اعتبارسنجی خودرو
    # ---------------------------------------------------------

    vehicle = get_vehicle(
        db,
        vehicle_id=vehicle_id,
    )

    validate_vehicle_for_trip(
        vehicle,
        trip,
    )

    # ---------------------------------------------------------
    # 3. بررسی دسترسی راننده
    # ---------------------------------------------------------

    if driver_id is not None:
        validate_driver_vehicle_access(
            driver_id,
            trip,
            vehicle,
        )

    # ---------------------------------------------------------
    # 4. بررسی زمان GPS
    # ---------------------------------------------------------

    validate_recorded_at(
        recorded_at,
    )

    normalized_recorded_at = recorded_at.astimezone(
        timezone.utc
    )

    # ---------------------------------------------------------
    # 5. ثبت موقعیت GPS
    # ---------------------------------------------------------

    location = VehicleLocation(
        trip_id=trip.id,
        vehicle_id=vehicle.id,
        latitude=latitude,
        longitude=longitude,
        speed=speed,
        heading=heading,
        recorded_at=normalized_recorded_at,
    )

    db.add(location)
    db.commit()
    db.refresh(location)

    # ---------------------------------------------------------
    # 6. ارسال موقعیت جدید به WebSocket
    # ---------------------------------------------------------

    await connection_manager.send_to_trip(
        trip.id,
        {
            "type": "vehicle_location",
            "trip_id": trip.id,
            "vehicle_id": vehicle.id,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "speed": location.speed,
            "heading": location.heading,
            "recorded_at": location.recorded_at.isoformat(),
        },
    )

    # ---------------------------------------------------------
    # 7. محاسبه و ارسال ETA
    # ---------------------------------------------------------

    try:
        eta_result = get_next_station(
            db,
            trip_id=trip.id,
        )

        if eta_result is not None:
            await connection_manager.send_to_trip(
                trip.id,
                {
                    "type": "vehicle_eta",
                    "trip_id": trip.id,
                    **eta_result,
                },
            )

    except Exception:
        # خطای ETA نباید باعث شکست ثبت GPS شود.
        pass

    # ---------------------------------------------------------
    # 8. تشخیص ورود / خروج از ایستگاه
    # ---------------------------------------------------------

    station_event = None

    try:
        station_event = detect_station_event(
            db,
            trip_id=trip.id,
        )

        if station_event is not None:
            await connection_manager.send_to_trip(
                trip.id,
                {
                    "type": "station_event",
                    **station_event,
                },
            )

    except Exception:
        # خطای تشخیص ایستگاه نباید ثبت GPS را خراب کند.
        pass

    # ---------------------------------------------------------
    # 9. بررسی رسیدن به آخرین ایستگاه
    # ---------------------------------------------------------

    completed_trip = None

    try:
        current_speed = float(
            location.speed
            if location.speed is not None
            else 0
        )

        completed_trip = (
            complete_trip_if_arrived_at_final_station(
                db,
                trip_id=trip.id,
                latitude=location.latitude,
                longitude=location.longitude,
                speed_kmh=current_speed,
                recorded_at=location.recorded_at,
            )
        )

        if completed_trip is not None:
            await connection_manager.send_to_trip(
                trip.id,
                {
                    "type": "trip_completed",
                    "trip_id": completed_trip.id,
                    "status": completed_trip.status,
                    "actual_arrival_time": (
                        completed_trip.actual_arrival_time.isoformat()
                        if completed_trip.actual_arrival_time
                        else None
                    ),
                },
            )

    except Exception:
        # خطای تکمیل خودکار سفر نباید
        # باعث از دست رفتن موقعیت GPS شود.
        pass

    # ---------------------------------------------------------
    # 10. خروجی نهایی
    # ---------------------------------------------------------

    return location