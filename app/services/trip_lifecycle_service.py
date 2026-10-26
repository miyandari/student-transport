from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.route_station import RouteStation
from app.models.station import Station
from app.models.trip import Trip
from app.services.station_event_service import calculate_distance_meters


FINAL_STATION_PROXIMITY_METERS = 100
FINAL_STATION_STOP_SPEED_KMH = 5


def get_trip_final_station(
    db: Session,
    *,
    trip_id: int,
):
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        return None

    if trip.service is None:
        return None

    route_id = trip.service.route_id

    final_route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == route_id,
        )
        .order_by(
            RouteStation.stop_order.desc(),
        )
        .first()
    )

    if final_route_station is None:
        return None

    station = (
        db.query(Station)
        .filter(
            Station.id == final_route_station.station_id,
        )
        .first()
    )

    if station is None:
        return None

    return final_route_station, station


def is_at_final_station(
    db: Session,
    *,
    trip_id: int,
    latitude: float,
    longitude: float,
    speed_kmh: float,
) -> bool:
    result = get_trip_final_station(
        db,
        trip_id=trip_id,
    )

    if result is None:
        return False

    _, station = result

    distance = calculate_distance_meters(
        latitude,
        longitude,
        station.latitude,
        station.longitude,
    )

    return (
        distance <= FINAL_STATION_PROXIMITY_METERS
        and speed_kmh < FINAL_STATION_STOP_SPEED_KMH
    )


def complete_trip_if_arrived_at_final_station(
    db: Session,
    *,
    trip_id: int,
    latitude: float,
    longitude: float,
    speed_kmh: float,
    recorded_at: datetime,
):
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        return None

    # سفرهای پایان‌یافته یا لغوشده دوباره تکمیل نمی‌شوند.
    if trip.status in {"completed", "cancelled"}:
        return None

    # فقط سفر در حال حرکت می‌تواند خودکار تکمیل شود.
    if trip.status != "in_progress":
        return None

    if not is_at_final_station(
        db,
        trip_id=trip_id,
        latitude=latitude,
        longitude=longitude,
        speed_kmh=speed_kmh,
    ):
        return None

    trip.status = "completed"
    trip.actual_arrival_time = recorded_at.astimezone(timezone.utc)

    db.commit()
    db.refresh(trip)

    return trip