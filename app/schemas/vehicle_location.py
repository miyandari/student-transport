from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


class VehicleLocationCreate(BaseModel):
    trip_id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed: float | None = None
    heading: float | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "recorded_at باید دارای timezone باشد"
            )

        return value.astimezone(timezone.utc)


class VehicleLocationResponse(BaseModel):
    id: int
    trip_id: int
    vehicle_id: int
    latitude: float
    longitude: float
    speed: float | None
    heading: float | None
    recorded_at: datetime

    class Config:
        from_attributes = True