from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.route_station import RouteStation
from app.models.station import Station
from app.models.trip import Trip
from app.models.vehicle_location import VehicleLocation


# -----------------------------
# تنظیمات ETA و GPS
# -----------------------------

MAX_HEADING_DEVIATION = 90

MIN_VALID_SPEED_KMH = 5
MAX_VALID_SPEED_KMH = 120

RECENT_LOCATION_COUNT = 5

STATION_PROXIMITY_METERS = 100

GPS_FRESH_THRESHOLD_SECONDS = 30
GPS_STALE_THRESHOLD_SECONDS = 90


# -----------------------------
# محاسبه فاصله
# -----------------------------

def calculate_distance_meters(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius = 6_371_000

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    a = max(0.0, min(1.0, a))

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a),
    )

    return earth_radius * c


# -----------------------------
# محاسبه جهت
# -----------------------------

def calculate_bearing(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)

    delta_lon = radians(lon2 - lon1)

    x = (
        sin(delta_lon)
        * cos(lat2_rad)
    )

    y = (
        cos(lat1_rad)
        * sin(lat2_rad)
        - sin(lat1_rad)
        * cos(lat2_rad)
        * cos(delta_lon)
    )

    bearing = atan2(x, y)

    bearing_degrees = (
        bearing * 180 / 3.141592653589793
    )

    return (bearing_degrees + 360) % 360


def calculate_heading_difference(
    heading: float,
    bearing: float,
) -> float:
    difference = abs(
        heading - bearing
    )

    return min(
        difference,
        360 - difference,
    )


# -----------------------------
# سرعت معتبر
# -----------------------------

def is_valid_speed(
    speed: float | None,
) -> bool:
    if speed is None:
        return False

    return (
        MIN_VALID_SPEED_KMH
        <= speed
        <= MAX_VALID_SPEED_KMH
    )


# -----------------------------
# سرعت مؤثر
# -----------------------------

def get_effective_speed(
    db: Session,
    trip_id: int,
) -> tuple[float | None, str]:
    latest_locations = (
        db.query(VehicleLocation)
        .filter(
            VehicleLocation.trip_id == trip_id
        )
        .order_by(
            VehicleLocation.recorded_at.desc()
        )
        .limit(RECENT_LOCATION_COUNT)
        .all()
    )

    if not latest_locations:
        return None, "unavailable"

    latest_speed = latest_locations[0].speed

    if is_valid_speed(latest_speed):
        return latest_speed, "latest"

    valid_speeds = [
        location.speed
        for location in latest_locations
        if is_valid_speed(location.speed)
    ]

    if not valid_speeds:
        return None, "unavailable"

    average_speed = (
        sum(valid_speeds)
        / len(valid_speeds)
    )

    return average_speed, "recent_average"


# -----------------------------
# وضعیت تازگی GPS
# -----------------------------

def get_gps_status(
    recorded_at: datetime,
) -> dict:
    if recorded_at.tzinfo is None:
        recorded_at_utc = recorded_at.replace(
            tzinfo=timezone.utc
        )
    else:
        recorded_at_utc = recorded_at.astimezone(
            timezone.utc
        )

    now = datetime.now(timezone.utc)

    age_seconds = (
        now - recorded_at_utc
    ).total_seconds()

    age_seconds = max(
        0,
        age_seconds,
    )

    if age_seconds <= GPS_FRESH_THRESHOLD_SECONDS:
        gps_status = "fresh"

    elif age_seconds <= GPS_STALE_THRESHOLD_SECONDS:
        gps_status = "stale"

    else:
        gps_status = "offline"

    return {
        "gps_status": gps_status,
        "gps_age_seconds": round(
            age_seconds,
            1,
        ),
    }


# -----------------------------
# وضعیت حرکت خودرو
# -----------------------------

def detect_vehicle_status(
    db: Session,
    trip: Trip,
    latest_location: VehicleLocation,
) -> dict:
    speed = latest_location.speed

    route_stations = get_route_stations(
        db,
        trip,
    )

    nearest_station = None
    nearest_distance = None

    for _, station in route_stations:
        distance = calculate_distance_meters(
            latest_location.latitude,
            latest_location.longitude,
            station.latitude,
            station.longitude,
        )

        if (
            nearest_distance is None
            or distance < nearest_distance
        ):
            nearest_distance = distance
            nearest_station = station

    if is_valid_speed(speed):
        return {
            "status": "moving",
            "station_id": None,
            "station_name": None,
            "distance_to_station_meters": None,
        }

    if (
        nearest_station is not None
        and nearest_distance is not None
        and nearest_distance
        <= STATION_PROXIMITY_METERS
    ):
        return {
            "status": "stopped_at_station",
            "station_id": nearest_station.id,
            "station_name": nearest_station.name,
            "distance_to_station_meters": round(
                nearest_distance,
                2,
            ),
        }

    return {
        "status": "stopped",
        "station_id": None,
        "station_name": None,
        "distance_to_station_meters": None,
    }


# -----------------------------
# ETA
# -----------------------------

def calculate_eta_seconds(
    distance_meters: float,
    speed_kmh: float,
) -> int:
    if distance_meters < 0:
        raise ValueError(
            "فاصله برای محاسبه ETA نمی‌تواند منفی باشد"
        )

    if speed_kmh <= 0:
        raise ValueError(
            "سرعت برای محاسبه ETA باید بیشتر از صفر باشد"
        )

    speed_meters_per_second = (
        speed_kmh / 3.6
    )

    eta_seconds = (
        distance_meters
        / speed_meters_per_second
    )

    return max(
        0,
        round(eta_seconds),
    )


# -----------------------------
# دریافت ایستگاه‌های مسیر
# -----------------------------

def get_route_stations(
    db: Session,
    trip: Trip,
) -> list[tuple[RouteStation, Station]]:
    if trip.service is None:
        return []

    return (
        db.query(
            RouteStation,
            Station,
        )
        .join(
            Station,
            Station.id
            == RouteStation.station_id,
        )
        .filter(
            RouteStation.route_id
            == trip.service.route_id,
            Station.is_active.is_(True),
        )
        .order_by(
            RouteStation.stop_order.asc()
        )
        .all()
    )


# -----------------------------
# خلاصه ایستگاه
# -----------------------------

def _station_summary(
    item: dict | None,
) -> dict | None:
    if item is None:
        return None

    return {
        "station_id": item["station"].id,
        "station_name": item["station"].name,
        "stop_order": item[
            "route_station"
        ].stop_order,
        "distance_meters": round(
            item["distance"],
            2,
        ),
    }


# -----------------------------
# تشخیص پیشرفت مسیر
# -----------------------------

def calculate_route_progress(
    db: Session,
    trip: Trip,
    latest_location: VehicleLocation,
) -> dict:
    route_stations = get_route_stations(
        db,
        trip,
    )

    if not route_stations:
        return {
            "previous_station": None,
            "next_station": None,
            "route_progress_percent": 0,
            "route_progress_status": "no_route_data",
        }

    vehicle_lat = latest_location.latitude
    vehicle_lon = latest_location.longitude

    station_data = []

    for route_station, station in route_stations:
        distance = calculate_distance_meters(
            vehicle_lat,
            vehicle_lon,
            station.latitude,
            station.longitude,
        )

        station_data.append(
            {
                "route_station": route_station,
                "station": station,
                "distance": distance,
            }
        )

    if len(station_data) == 1:
        only_station = station_data[0]

        if (
            only_station["distance"]
            <= STATION_PROXIMITY_METERS
        ):
            return {
                "previous_station":
                    _station_summary(
                        only_station
                    ),
                "next_station": None,
                "route_progress_percent": 100,
                "route_progress_status":
                    "at_final_station",
            }

        return {
            "previous_station": None,
            "next_station":
                _station_summary(
                    only_station
                ),
            "route_progress_percent": 0,
            "route_progress_status":
                "before_first_station",
        }

    nearest = min(
        station_data,
        key=lambda item: item["distance"],
    )

    # ---------------------------------
    # خودرو دقیقاً نزدیک یک ایستگاه است
    # ---------------------------------

    if (
        nearest["distance"]
        <= STATION_PROXIMITY_METERS
    ):
        current_index = next(
            (
                index
                for index, item
                in enumerate(station_data)
                if item["route_station"].id
                == nearest["route_station"].id
            ),
            0,
        )

        if current_index + 1 < len(
            station_data
        ):
            next_item = station_data[
                current_index + 1
            ]

            return {
                "previous_station":
                    _station_summary(
                        nearest
                    ),
                "next_station":
                    _station_summary(
                        next_item
                    ),
                "route_progress_percent":
                    round(
                        (
                            current_index
                            / max(
                                1,
                                len(station_data)
                                - 1,
                            )
                        )
                        * 100,
                        1,
                    ),
                "route_progress_status":
                    "at_station",
            }

        return {
            "previous_station":
                _station_summary(
                    nearest
                ),
            "next_station": None,
            "route_progress_percent": 100,
            "route_progress_status":
                "at_final_station",
        }

    # ---------------------------------
    # تشخیص بازه فعلی مسیر
    # ---------------------------------

    previous_station = None
    next_station = None

    for index in range(
        len(station_data) - 1
    ):
        current_item = station_data[index]
        next_item = station_data[index + 1]

        current_order = (
            current_item[
                "route_station"
            ].stop_order
        )

        next_order = (
            next_item[
                "route_station"
            ].stop_order
        )

        if next_order <= current_order:
            continue

        # از دو ایستگاه مجاور، نزدیک‌ترین
        # ایستگاه را مبنای تخمین قرار می‌دهیم.
        if (
            current_item["distance"]
            <= next_item["distance"]
        ):
            previous_station = current_item
            next_station = next_item
        else:
            previous_station = current_item
            next_station = next_item

        break

    # ---------------------------------
    # fallback
    # ---------------------------------

    if next_station is None:
        next_candidates = [
            item
            for item in station_data
            if item[
                "route_station"
            ].stop_order
            > nearest[
                "route_station"
            ].stop_order
        ]

        if next_candidates:
            next_station = min(
                next_candidates,
                key=lambda item:
                    item[
                        "route_station"
                    ].stop_order,
            )

            previous_candidates = [
                item
                for item in station_data
                if item[
                    "route_station"
                ].stop_order
                < next_station[
                    "route_station"
                ].stop_order
            ]

            if previous_candidates:
                previous_station = max(
                    previous_candidates,
                    key=lambda item:
                        item[
                            "route_station"
                        ].stop_order,
                )

    if (
        previous_station is None
        and next_station is None
    ):
        return {
            "previous_station": None,
            "next_station": None,
            "route_progress_percent": 0,
            "route_progress_status":
                "progress_unknown",
        }

    # ---------------------------------
    # درصد پیشرفت مسیر
    # ---------------------------------

    first_order = (
        station_data[0][
            "route_station"
        ].stop_order
    )

    last_order = (
        station_data[-1][
            "route_station"
        ].stop_order
    )

    order_range = max(
        1,
        last_order - first_order,
    )

    if previous_station is None:
        progress_percent = 0

    elif next_station is None:
        progress_percent = 100

    else:
        previous_order = (
            previous_station[
                "route_station"
            ].stop_order
        )

        next_order = (
            next_station[
                "route_station"
            ].stop_order
        )

        segment_distance = (
            calculate_distance_meters(
                previous_station[
                    "station"
                ].latitude,
                previous_station[
                    "station"
                ].longitude,
                next_station[
                    "station"
                ].latitude,
                next_station[
                    "station"
                ].longitude,
            )
        )

        previous_distance = (
            previous_station["distance"]
        )

        next_distance = (
            next_station["distance"]
        )

        distance_sum = (
            previous_distance
            + next_distance
        )

        if (
            segment_distance > 0
            and distance_sum > 0
        ):
            segment_progress = (
                previous_distance
                / distance_sum
            )
        else:
            segment_progress = 0

        segment_progress = max(
            0,
            min(
                1,
                segment_progress,
            ),
        )

        base_progress = (
            previous_order
            - first_order
        ) / order_range

        segment_count = max(
            1,
            next_order - previous_order,
        )

        progress_percent = (
            base_progress
            + (
                segment_progress
                * segment_count
                / order_range
            )
        ) * 100

    return {
        "previous_station":
            _station_summary(
                previous_station
            ),
        "next_station":
            _station_summary(
                next_station
            ),
        "route_progress_percent":
            round(
                max(
                    0,
                    min(
                        100,
                        progress_percent,
                    ),
                ),
                1,
            ),
        "route_progress_status":
            "between_stations",
    }


# -----------------------------
# محاسبه ETA ایستگاه‌های بعدی
# -----------------------------

def _calculate_upcoming_station_eta(
    *,
    route_stations: list[
        tuple[RouteStation, Station]
    ],
    next_index: int,
    effective_speed: float | None,
    gps_status: str,
    vehicle_latitude: float,
    vehicle_longitude: float,
    first_eta_seconds: int | None,
) -> list[dict]:
    upcoming_stations = []

    if (
        gps_status == "offline"
        or effective_speed is None
        or effective_speed <= 0
    ):
        first_eta_seconds = None

    accumulated_eta = first_eta_seconds

    for index in range(
        next_index + 1,
        len(route_stations),
    ):
        previous_route_station, previous_station = (
            route_stations[index - 1]
        )

        route_station, station = (
            route_stations[index]
        )

        if accumulated_eta is not None:
            accumulated_eta += (
                previous_route_station
                .stop_duration_seconds
                or 0
            )

            segment_distance = (
                calculate_distance_meters(
                    previous_station.latitude,
                    previous_station.longitude,
                    station.latitude,
                    station.longitude,
                )
            )

            segment_eta = (
                calculate_eta_seconds(
                    segment_distance,
                    effective_speed,
                )
            )

            accumulated_eta += segment_eta

            station_eta = accumulated_eta

        else:
            station_eta = None

        distance_from_vehicle = (
            calculate_distance_meters(
                vehicle_latitude,
                vehicle_longitude,
                station.latitude,
                station.longitude,
            )
        )

        station_bearing = calculate_bearing(
            vehicle_latitude,
            vehicle_longitude,
            station.latitude,
            station.longitude,
        )

        upcoming_stations.append(
            {
                "station_id": station.id,
                "station_name": station.name,
                "stop_order":
                    route_station.stop_order,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "distance_from_vehicle_meters":
                    round(
                        distance_from_vehicle,
                        2,
                    ),
                "estimated_minutes_from_start":
                    route_station
                    .estimated_minutes_from_start,
                "stop_duration_seconds":
                    route_station
                    .stop_duration_seconds,
                "station_bearing":
                    round(
                        station_bearing,
                        2,
                    ),
                "heading_difference": None,
                "eta_seconds": station_eta,
            }
        )

    return upcoming_stations


# -----------------------------
# موتور اصلی ETA
# -----------------------------

def get_next_station(
    db: Session,
    *,
    trip_id: int,
) -> dict:
    trip = (
        db.query(Trip)
        .filter(
            Trip.id == trip_id
        )
        .first()
    )

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )

    latest_location = (
        db.query(VehicleLocation)
        .filter(
            VehicleLocation.trip_id
            == trip.id
        )
        .order_by(
            VehicleLocation.recorded_at.desc()
        )
        .first()
    )

    if not latest_location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="هنوز موقعیتی برای این سفر ثبت نشده است",
        )

    gps_status = get_gps_status(
        latest_location.recorded_at
    )

    route_stations = get_route_stations(
        db,
        trip,
    )

    if not route_stations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سفر ایستگاه مسیری ثبت نشده است",
        )

    effective_speed, speed_source = (
        get_effective_speed(
            db,
            trip.id,
        )
    )

    vehicle_status = detect_vehicle_status(
        db,
        trip,
        latest_location,
    )

    route_progress = calculate_route_progress(
        db,
        trip,
        latest_location,
    )

    next_station_summary = (
        route_progress["next_station"]
    )

    if next_station_summary is None:
        return {
            "trip_id": trip.id,
            "vehicle_id":
                latest_location.vehicle_id,
            "vehicle_latitude":
                latest_location.latitude,
            "vehicle_longitude":
                latest_location.longitude,
            "vehicle_heading":
                latest_location.heading,
            "vehicle_speed_kmh":
                latest_location.speed,
            "effective_speed_kmh":
                effective_speed,
            "speed_source":
                speed_source,
            "gps_status":
                gps_status["gps_status"],
            "gps_age_seconds":
                gps_status["gps_age_seconds"],
            "eta_available": False,
            "vehicle_status":
                vehicle_status,
            "previous_station":
                route_progress[
                    "previous_station"
                ],
            "next_station": None,
            "route_progress_percent":
                route_progress[
                    "route_progress_percent"
                ],
            "route_progress_status":
                route_progress[
                    "route_progress_status"
                ],
            "upcoming_stations": [],
        }

    next_station_id = (
        next_station_summary["station_id"]
    )

    next_route_station = None
    next_station = None
    next_station_index = None

    for index, (
        route_station,
        station,
    ) in enumerate(route_stations):
        if station.id == next_station_id:
            next_route_station = route_station
            next_station = station
            next_station_index = index
            break

    if (
        next_route_station is None
        or next_station is None
        or next_station_index is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اطلاعات ایستگاه بعدی کامل نیست",
        )

    distance_to_next_station = (
        calculate_distance_meters(
            latest_location.latitude,
            latest_location.longitude,
            next_station.latitude,
            next_station.longitude,
        )
    )

    station_bearing = calculate_bearing(
        latest_location.latitude,
        latest_location.longitude,
        next_station.latitude,
        next_station.longitude,
    )

    heading_difference = None

    if latest_location.heading is not None:
        heading_difference = (
            calculate_heading_difference(
                latest_location.heading,
                station_bearing,
            )
        )

    # -----------------------------
    # بررسی جهت حرکت
    # -----------------------------

    heading_is_valid = True

    if (
        latest_location.heading is not None
        and is_valid_speed(
            latest_location.speed
        )
    ):
        heading_is_valid = (
            heading_difference is None
            or heading_difference
            <= MAX_HEADING_DEVIATION
        )

    # -----------------------------
    # ETA ایستگاه بعدی
    # -----------------------------

    next_station_eta = None

    if (
        gps_status["gps_status"]
        != "offline"
        and effective_speed is not None
        and effective_speed > 0
        and heading_is_valid
    ):
        next_station_eta = (
            calculate_eta_seconds(
                distance_to_next_station,
                effective_speed,
            )
        )

    # -----------------------------
    # ایستگاه‌های بعدی
    # -----------------------------

    upcoming_stations = (
        _calculate_upcoming_station_eta(
            route_stations=route_stations,
            next_index=next_station_index,
            effective_speed=effective_speed,
            gps_status=gps_status[
                "gps_status"
            ],
            vehicle_latitude=
                latest_location.latitude,
            vehicle_longitude=
                latest_location.longitude,
            first_eta_seconds=
                next_station_eta,
        )
    )

    # -----------------------------
    # افزودن heading واقعی
    # -----------------------------

    for item in upcoming_stations:
        station_heading = item[
            "station_bearing"
        ]

        if latest_location.heading is not None:
            item["heading_difference"] = round(
                calculate_heading_difference(
                    latest_location.heading,
                    station_heading,
                ),
                2,
            )

    # -----------------------------
    # خروجی ایستگاه بعدی
    # -----------------------------

    next_station_data = {
        "station_id":
            next_station.id,
        "station_name":
            next_station.name,
        "stop_order":
            next_route_station.stop_order,
        "latitude":
            next_station.latitude,
        "longitude":
            next_station.longitude,
        "distance_from_vehicle_meters":
            round(
                distance_to_next_station,
                2,
            ),
        "estimated_minutes_from_start":
            next_route_station
            .estimated_minutes_from_start,
        "stop_duration_seconds":
            next_route_station
            .stop_duration_seconds,
        "station_bearing":
            round(
                station_bearing,
                2,
            ),
        "heading_difference":
            (
                round(
                    heading_difference,
                    2,
                )
                if heading_difference is not None
                else None
            ),
        "eta_seconds":
            next_station_eta,
    }

    return {
        "trip_id":
            trip.id,
        "vehicle_id":
            latest_location.vehicle_id,
        "vehicle_latitude":
            latest_location.latitude,
        "vehicle_longitude":
            latest_location.longitude,
        "vehicle_heading":
            latest_location.heading,
        "vehicle_speed_kmh":
            latest_location.speed,
        "effective_speed_kmh":
            effective_speed,
        "speed_source":
            speed_source,
        "gps_status":
            gps_status["gps_status"],
        "gps_age_seconds":
            gps_status["gps_age_seconds"],
        "eta_available":
            next_station_eta is not None,
        "heading_is_valid":
            heading_is_valid,
        "vehicle_status":
            vehicle_status,
        "previous_station":
            route_progress[
                "previous_station"
            ],
        "next_station":
            next_station_data,
        "route_progress_percent":
            route_progress[
                "route_progress_percent"
            ],
        "route_progress_status":
            route_progress[
                "route_progress_status"
            ],
        "upcoming_stations":
            [
                next_station_data,
                *upcoming_stations,
            ],
    }