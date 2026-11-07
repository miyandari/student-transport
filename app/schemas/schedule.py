from datetime import time

from pydantic import BaseModel, Field, field_validator


class ScheduleCreate(BaseModel):
    university_id: int
    service_id: int

    day_of_week: int = Field(
        ge=0,
        le=6,
    )

    departure_time: time
    arrival_time: time | None = None

    schedule_type: str = Field(
        min_length=1,
        max_length=50,
    )

    is_active: bool = True

    default_driver_id: int | None = None
    default_vehicle_id: int | None = None

    @field_validator("university_id", "service_id")
    @classmethod
    def validate_positive_ids(
        cls,
        value: int,
    ) -> int:
        if value <= 0:
            raise ValueError(
                "شناسه باید عددی مثبت باشد"
            )

        return value

    @field_validator("default_driver_id", "default_vehicle_id")
    @classmethod
    def validate_default_ids(
        cls,
        value: int | None,
    ) -> int | None:
        if value is not None and value <= 0:
            raise ValueError(
                "شناسه باید عددی مثبت باشد"
            )

        return value

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "نوع برنامه زمانی نمی‌تواند خالی باشد"
            )

        return value

    @field_validator("arrival_time")
    @classmethod
    def validate_arrival_time(
        cls,
        value: time | None,
        info,
    ) -> time | None:
        if value is None:
            return value

        departure_time = info.data.get(
            "departure_time"
        )

        if (
            departure_time is not None
            and value <= departure_time
        ):
            raise ValueError(
                "ساعت رسیدن باید بعد از ساعت حرکت باشد"
            )

        return value


class ScheduleResponse(BaseModel):
    id: int
    university_id: int
    service_id: int
    day_of_week: int
    departure_time: time
    arrival_time: time | None
    schedule_type: str
    is_active: bool
    default_driver_id: int | None = None
    default_vehicle_id: int | None = None

    class Config:
        from_attributes = True
