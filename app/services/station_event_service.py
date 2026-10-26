from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.route_station import RouteStation
from app.models.station import Station
from app.models.station_event import StationEvent
from app.models.trip import Trip
from app.models.vehicle_location import VehicleLocation


STATION_ARRIVAL_DISTANCE_METERS = 100
STATION_DEPARTURE_DISTANCE_METERS = 150
STATION_STOP_SPEED_KMH = 5


def calculate_distance_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    from math import atan2, cos, radians, sin, sqrt

    earth_radius = 6_371_000

    lat1 = radians(latitude1)
    lat2 = radians(latitude2)

    delta_lat = radians(latitude2 - latitude1)
    delta_lon = radians(longitude2 - longitude1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(delta_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c


def get_latest_locations(
    db: Session,
    *,
    trip_id: int,
    limit: int = 2,
) -> list[VehicleLocation]:
    return (
        db.query(VehicleLocation)
        .filter(
            VehicleLocation.trip_id == trip_id,
        )
        .order_by(
            VehicleLocation.recorded_at.desc(),
        )
        .limit(limit)
        .all()
    )


def get_route_stations(
    db: Session,
    *,
    trip_id: int,
) -> list[tuple[RouteStation, Station]]:
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if trip is None:
        return []

    rows = (
        db.query(RouteStation, Station)
        .join(
            Station,
            Station.id == RouteStation.station_id,
        )
        .filter(
            RouteStation.route_id == trip.service.route_id,
            Station.university_id == trip.university_id,
            Station.is_active.is_(True),
        )
        .order_by(
            RouteStation.stop_order.asc(),
        )
        .all()
    )

    return rows


def save_station_event(
    db: Session,
    *,
    trip_id: int,
    station_id: int,
    event_type: str,
    distance_meters: float,
    speed_kmh: float,
    recorded_at: datetime,
) -> StationEvent:
    event = StationEvent(
        trip_id=trip_id,
        station_id=station_id,
        event_type=event_type,
        distance_meters=distance_meters,
        speed_kmh=speed_kmh,
        recorded_at=recorded_at,
        created_at=datetime.now(timezone.utc),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def detect_station_event(
    db: Session,
    *,
    trip_id: int,
):
    locations = get_latest_locations(
        db,
        trip_id=trip_id,
        limit=2,
    )

    if len(locations) < 2:
        return None

    latest = locations[0]
    previous = locations[1]

    route_stations = get_route_stations(
        db,
        trip_id=trip_id,
    )

    if not route_stations:
        return None

    nearest_station = None
    nearest_route_station = None
    nearest_distance = None

    for route_station, station in route_stations:
        distance = calculate_distance_meters(
            latest.latitude,
            latest.longitude,
            station.latitude,
            station.longitude,
        )

        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_station = station
            nearest_route_station = route_station

    if (
        nearest_station is None
        or nearest_route_station is None
        or nearest_distance is None
    ):
        return None

    previous_distance = calculate_distance_meters(
        previous.latitude,
        previous.longitude,
        nearest_station.latitude,
        nearest_station.longitude,
    )

    current_speed = float(
        latest.speed
        if latest.speed is not None
        else 0
    )

    event_type = None

    # تشخیص ورود به ایستگاه
    if (
        previous_distance > STATION_ARRIVAL_DISTANCE_METERS
        and nearest_distance <= STATION_ARRIVAL_DISTANCE_METERS
        and current_speed < STATION_STOP_SPEED_KMH
    ):
        event_type = "arrived"

    # تشخیص خروج از ایستگاه
    elif (
        previous_distance <= STATION_ARRIVAL_DISTANCE_METERS
        and nearest_distance >= STATION_DEPARTURE_DISTANCE_METERS
        and current_speed >= STATION_STOP_SPEED_KMH
    ):
        event_type = "departed"

    if event_type is None:
        return None

    # جلوگیری از ثبت رویداد تکراری
    last_event = (
        db.query(StationEvent)
        .filter(
            StationEvent.trip_id == trip_id,
            StationEvent.station_id == nearest_station.id,
        )
        .order_by(
            StationEvent.recorded_at.desc(),
        )
        .first()
    )

    if last_event is not None:
        # ترتیب معتبر رویدادها:
        # arrived -> departed
        #
        # اگر آخرین رویداد arrived باشد،
        # ثبت arrived جدید مجاز نیست.
        if (
            event_type == "arrived"
            and last_event.event_type == "arrived"
        ):
            return None

        # اگر آخرین رویداد departed باشد،
        # برای همین ایستگاه در همین سفر دوباره رویداد ثبت نمی‌کنیم.
        if (
            event_type == "arrived"
            and last_event.event_type == "departed"
        ):
            return None

        # departed فقط زمانی معتبر است
        # که قبل از آن arrived ثبت شده باشد.
        if (
            event_type == "departed"
            and last_event.event_type != "arrived"
        ):
            return None

    event = save_station_event(
        db,
        trip_id=trip_id,
        station_id=nearest_station.id,
        event_type=event_type,
        distance_meters=nearest_distance,
        speed_kmh=current_speed,
        recorded_at=latest.recorded_at,
    )

    return {
        "station_event_id": event.id,
        "trip_id": trip_id,
        "station_id": nearest_station.id,
        "station_name": nearest_station.name,
        "stop_order": nearest_route_station.stop_order,
        "event_type": event.event_type,
        "distance_meters": event.distance_meters,
        "speed_kmh": event.speed_kmh,
        "recorded_at": event.recorded_at,
    }


def get_station_events(
    db: Session,
    *,
    trip_id: int,
    station_id: int | None = None,
) -> list[StationEvent]:
    query = (
        db.query(StationEvent)
        .filter(
            StationEvent.trip_id == trip_id,
        )
    )

    if station_id is not None:
        query = query.filter(
            StationEvent.station_id == station_id,
        )

    return (
        query
        .order_by(
            StationEvent.recorded_at.asc(),
        )
        .all()
    )


def get_station_stop_duration(
    db: Session,
    *,
    trip_id: int,
    station_id: int,
):
    arrival = (
        db.query(StationEvent)
        .filter(
            StationEvent.trip_id == trip_id,
            StationEvent.station_id == station_id,
            StationEvent.event_type == "arrived",
        )
        .order_by(
            StationEvent.recorded_at.desc(),
        )
        .first()
    )

    if arrival is None:
        return None

    departure = (
        db.query(StationEvent)
        .filter(
            StationEvent.trip_id == trip_id,
            StationEvent.station_id == station_id,
            StationEvent.event_type == "departed",
            StationEvent.recorded_at > arrival.recorded_at,
        )
        .order_by(
            StationEvent.recorded_at.asc(),
        )
        .first()
    )

    if departure is None:
        return None

    route_station = (
        db.query(RouteStation)
        .filter(
            RouteStation.route_id == (
                db.query(Trip)
                .filter(Trip.id == trip_id)
                .scalar_subquery()
            ),
            RouteStation.station_id == station_id,
        )
        .first()
    )

    if route_station is None:
        return None

    actual_stop_seconds = int(
        (
            departure.recorded_at
            - arrival.recorded_at
        ).total_seconds()
    )

    planned_stop_seconds = int(
        route_station.stop_duration_seconds or 0
    )

    stop_delay_seconds = (
        actual_stop_seconds
        - planned_stop_seconds
    )

    station = (
        db.query(Station)
        .filter(Station.id == station_id)
        .first()
    )

    if station is None:
        return None

    return {
        "trip_id": trip_id,
        "station_id": station_id,
        "station_name": station.name,
        "arrival_time": arrival.recorded_at,
        "departure_time": departure.recorded_at,
        "actual_stop_seconds": actual_stop_seconds,
        "planned_stop_seconds": planned_stop_seconds,
        "stop_delay_seconds": stop_delay_seconds,
    }


def get_trip_station_report(
    db: Session,
    *,
    trip_id: int,
):
    route_stations = get_route_stations(
        db,
        trip_id=trip_id,
    )

    events = get_station_events(
        db,
        trip_id=trip_id,
    )

    report = []

    for route_station, station in route_stations:
        station_events = [
            event
            for event in events
            if event.station_id == station.id
        ]

        arrival_event = next(
            (
                event
                for event in station_events
                if event.event_type == "arrived"
            ),
            None,
        )

        departure_event = next(
            (
                event
                for event in station_events
                if (
                    event.event_type == "departed"
                    and (
                        arrival_event is None
                        or event.recorded_at
                        > arrival_event.recorded_at
                    )
                )
            ),
            None,
        )

        actual_stop_seconds = None

        if arrival_event and departure_event:
            actual_stop_seconds = int(
                (
                    departure_event.recorded_at
                    - arrival_event.recorded_at
                ).total_seconds()
            )

        planned_stop_seconds = int(
            route_station.stop_duration_seconds or 0
        )

        stop_delay_seconds = None

        if actual_stop_seconds is not None:
            stop_delay_seconds = (
                actual_stop_seconds
                - planned_stop_seconds
            )

        report.append(
            {
                "station_id": station.id,
                "station_name": station.name,
                "stop_order": route_station.stop_order,
                "arrival_time": (
                    arrival_event.recorded_at
                    if arrival_event
                    else None
                ),
                "departure_time": (
                    departure_event.recorded_at
                    if departure_event
                    else None
                ),
                "actual_stop_seconds": actual_stop_seconds,
                "planned_stop_seconds": planned_stop_seconds,
                "stop_delay_seconds": stop_delay_seconds,
            }
        )

    return report


def get_trip_delay_report(
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
        return []

    route_stations = get_route_stations(
        db,
        trip_id=trip_id,
    )

    events = get_station_events(
        db,
        trip_id=trip_id,
    )

    if not route_stations:
        return []

    planned_departure = trip.planned_departure_time

    report = []

    for route_station, station in route_stations:
        arrival_event = next(
            (
                event
                for event in events
                if (
                    event.station_id == station.id
                    and event.event_type == "arrived"
                )
            ),
            None,
        )

        departure_event = next(
            (
                event
                for event in events
                if (
                    event.station_id == station.id
                    and event.event_type == "departed"
                    and (
                        arrival_event is None
                        or event.recorded_at
                        > arrival_event.recorded_at
                    )
                )
            ),
            None,
        )

        planned_arrival_time = None
        planned_departure_time = None

        if planned_departure is not None:
            planned_arrival_time = (
                planned_departure
                + timedelta(
                    minutes=(
                        route_station.estimated_minutes_from_start
                        or 0
                    )
                )
            )

            planned_departure_time = (
                planned_arrival_time
                + timedelta(
                    seconds=(
                        route_station.stop_duration_seconds
                        or 0
                    )
                )
            )

        actual_arrival_time = (
            arrival_event.recorded_at
            if arrival_event
            else None
        )

        actual_departure_time = (
            departure_event.recorded_at
            if departure_event
            else None
        )

        arrival_delay_seconds = None
        departure_delay_seconds = None

        if (
            actual_arrival_time is not None
            and planned_arrival_time is not None
        ):
            arrival_delay_seconds = int(
                (
                    actual_arrival_time
                    - planned_arrival_time
                ).total_seconds()
            )

        if (
            actual_departure_time is not None
            and planned_departure_time is not None
        ):
            departure_delay_seconds = int(
                (
                    actual_departure_time
                    - planned_departure_time
                ).total_seconds()
            )

        actual_stop_seconds = None

        if arrival_event and departure_event:
            actual_stop_seconds = int(
                (
                    departure_event.recorded_at
                    - arrival_event.recorded_at
                ).total_seconds()
            )

        planned_stop_seconds = int(
            route_station.stop_duration_seconds or 0
        )

        stop_delay_seconds = None

        if actual_stop_seconds is not None:
            stop_delay_seconds = (
                actual_stop_seconds
                - planned_stop_seconds
            )

        report.append(
            {
                "station_id": station.id,
                "station_name": station.name,
                "stop_order": route_station.stop_order,
                "planned_arrival_time": planned_arrival_time,
                "actual_arrival_time": actual_arrival_time,
                "planned_departure_time": planned_departure_time,
                "actual_departure_time": actual_departure_time,
                "arrival_delay_seconds": arrival_delay_seconds,
                "departure_delay_seconds": departure_delay_seconds,
                "actual_stop_seconds": actual_stop_seconds,
                "planned_stop_seconds": planned_stop_seconds,
                "stop_delay_seconds": stop_delay_seconds,
            }
        )

    return report


def get_trip_delay_summary(
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

    delay_report = get_trip_delay_report(
        db,
        trip_id=trip_id,
    )

    valid_arrival_delays = [
        item
        for item in delay_report
        if item["arrival_delay_seconds"] is not None
    ]

    arrival_delays = [
        item["arrival_delay_seconds"]
        for item in valid_arrival_delays
    ]

    total_delay_seconds = None

    if arrival_delays:
        total_delay_seconds = max(
            arrival_delays
        )

    average_arrival_delay_seconds = None

    if arrival_delays:
        average_arrival_delay_seconds = round(
            sum(arrival_delays)
            / len(arrival_delays)
        )

    max_arrival_delay_seconds = None
    max_delay_station_id = None
    max_delay_station_name = None

    if valid_arrival_delays:
        max_item = max(
            valid_arrival_delays,
            key=lambda item: item["arrival_delay_seconds"],
        )

        max_arrival_delay_seconds = (
            max_item["arrival_delay_seconds"]
        )

        max_delay_station_id = (
            max_item["station_id"]
        )

        max_delay_station_name = (
            max_item["station_name"]
        )

    delay_start_station_id = None
    delay_start_station_name = None

    for item in delay_report:
        arrival_delay = item["arrival_delay_seconds"]

        if arrival_delay is not None and arrival_delay > 0:
            delay_start_station_id = item["station_id"]
            delay_start_station_name = item["station_name"]
            break

    planned_arrival_time = None

    if delay_report:
        planned_arrival_time = (
            delay_report[-1]["planned_arrival_time"]
        )

    actual_arrival_time = trip.actual_arrival_time

    if actual_arrival_time is None and delay_report:
        last_station = delay_report[-1]

        actual_arrival_time = (
            last_station["actual_departure_time"]
            or last_station["actual_arrival_time"]
        )

    if total_delay_seconds is None or total_delay_seconds <= 0:
        delay_status = "on_time"
    elif total_delay_seconds <= 300:
        delay_status = "minor_delay"
    elif total_delay_seconds <= 900:
        delay_status = "delayed"
    else:
        delay_status = "severe_delay"

    return {
        "trip_id": trip.id,

        "planned_departure_time": (
            trip.planned_departure_time
        ),

        "actual_departure_time": (
            trip.actual_departure_time
        ),

        "planned_arrival_time": (
            planned_arrival_time
        ),

        "actual_arrival_time": (
            actual_arrival_time
        ),

        "total_delay_seconds": (
            total_delay_seconds
        ),

        "average_arrival_delay_seconds": (
            average_arrival_delay_seconds
        ),

        "max_arrival_delay_seconds": (
            max_arrival_delay_seconds
        ),

        "delay_start_station_id": (
            delay_start_station_id
        ),

        "delay_start_station_name": (
            delay_start_station_name
        ),

        "max_delay_station_id": (
            max_delay_station_id
        ),

        "max_delay_station_name": (
            max_delay_station_name
        ),

        "status": delay_status,
    }