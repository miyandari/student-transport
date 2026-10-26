from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class TripIncidentCreate(BaseModel):
    trip_id: int
    reported_by_driver_id: int | None = None
    incident_type: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    occurred_at: datetime

    @field_validator("incident_type")
    @classmethod
    def validate_incident_type(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "نوع حادثه نمی‌تواند خالی باشد"
            )

        return value

    @field_validator("description")
    @classmethod
    def normalize_description(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value if value else None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "زمان وقوع حادثه باید دارای منطقه زمانی باشد"
            )

        return value.astimezone(timezone.utc)


class TripIncidentResponse(BaseModel):
    id: int
    trip_id: int
    reported_by_driver_id: int | None
    incident_type: str
    description: str | None
    occurred_at: datetime
    resolved_at: datetime | None
    is_resolved: bool

    class Config:
        from_attributes = True