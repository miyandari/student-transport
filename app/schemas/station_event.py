from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StationEventResponse(BaseModel):
    id: int
    trip_id: int
    station_id: int
    event_type: str
    distance_meters: float
    speed_kmh: float
    recorded_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationStopDurationResponse(BaseModel):
    trip_id: int
    station_id: int
    station_name: str

    arrival_time: datetime
    departure_time: datetime

    actual_stop_seconds: int
    planned_stop_seconds: int
    stop_delay_seconds: int

    model_config = ConfigDict(from_attributes=True)


class TripStationReportItem(BaseModel):
    station_id: int
    station_name: str
    stop_order: int

    arrival_time: datetime | None
    departure_time: datetime | None

    actual_stop_seconds: int | None
    planned_stop_seconds: int

    stop_delay_seconds: int | None

    model_config = ConfigDict(from_attributes=True)


class TripDelayReportItem(BaseModel):
    station_id: int
    station_name: str
    stop_order: int

    planned_arrival_time: datetime | None
    actual_arrival_time: datetime | None

    planned_departure_time: datetime | None
    actual_departure_time: datetime | None

    arrival_delay_seconds: int | None
    departure_delay_seconds: int | None

    actual_stop_seconds: int | None
    planned_stop_seconds: int

    stop_delay_seconds: int | None

    model_config = ConfigDict(from_attributes=True)


class TripDelaySummaryResponse(BaseModel):
    trip_id: int

    planned_departure_time: datetime | None
    actual_departure_time: datetime | None

    planned_arrival_time: datetime | None
    actual_arrival_time: datetime | None

    total_delay_seconds: int | None

    average_arrival_delay_seconds: int | None
    max_arrival_delay_seconds: int | None

    delay_start_station_id: int | None
    delay_start_station_name: str | None

    max_delay_station_id: int | None
    max_delay_station_name: str | None

    status: str

    model_config = ConfigDict(from_attributes=True)