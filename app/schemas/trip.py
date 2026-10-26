from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ALLOWED_TRIP_STATUSES = {
    "scheduled",
    "boarding",
    "in_progress",
    "completed",
    "cancelled",
}


def _validate_positive_id(
    value: int,
    field_name: str,
) -> int:
    if value <= 0:
        raise ValueError(
            f"{field_name} باید عددی مثبت باشد"
        )

    return value


def _normalize_status(value: str) -> str:
    value = value.strip().lower()

    if value not in ALLOWED_TRIP_STATUSES:
        raise ValueError(
            "وضعیت سفر نامعتبر است"
        )

    return value


def _normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError(
            "زمان حرکت برنامه‌ریزی‌شده باید دارای منطقه زمانی باشد"
        )

    if value.utcoffset() is None:
        raise ValueError(
            "زمان حرکت برنامه‌ریزی‌شده معتبر نیست"
        )

    return value.astimezone(timezone.utc)


def _validate_capacity_rules(
    seated_capacity: int | None,
    standing_capacity: int | None,
    allow_standing: bool,
) -> None:
    if seated_capacity is not None and seated_capacity <= 0:
        raise ValueError(
            "ظرفیت صندلی باید بیشتر از صفر باشد"
        )

    if standing_capacity is not None and standing_capacity < 0:
        raise ValueError(
            "ظرفیت ایستاده نمی‌تواند منفی باشد"
        )

    if not allow_standing:
        if standing_capacity not in (None, 0):
            raise ValueError(
                "وقتی ایستادن مجاز نیست، ظرفیت ایستاده باید صفر یا خالی باشد"
            )

    if allow_standing:
        if standing_capacity is None or standing_capacity <= 0:
            raise ValueError(
                "وقتی ایستادن مجاز است، ظرفیت ایستاده باید بیشتر از صفر باشد"
            )


class TripCreate(BaseModel):
    university_id: int
    service_id: int
    schedule_id: int | None = None

    driver_id: int | None = None
    vehicle_id: int | None = None

    seated_capacity: int | None = Field(
        default=None,
        gt=0,
    )

    standing_capacity: int | None = Field(
        default=None,
        ge=0,
    )

    allow_standing: bool = False

    trip_date: date
    planned_departure_time: datetime

    status: str = "scheduled"
    is_active: bool = True

    @field_validator(
        "university_id",
        "service_id",
    )
    @classmethod
    def validate_required_ids(
        cls,
        value: int,
        info,
    ) -> int:
        field_names = {
            "university_id": "شناسه دانشگاه",
            "service_id": "شناسه سرویس",
        }

        return _validate_positive_id(
            value,
            field_names.get(
                info.field_name,
                "شناسه",
            ),
        )

    @field_validator(
        "schedule_id",
        "driver_id",
        "vehicle_id",
    )
    @classmethod
    def validate_optional_ids(
        cls,
        value: int | None,
        info,
    ) -> int | None:
        if value is None:
            return value

        field_names = {
            "schedule_id": "شناسه برنامه زمانی",
            "driver_id": "شناسه راننده",
            "vehicle_id": "شناسه خودرو",
        }

        return _validate_positive_id(
            value,
            field_names.get(
                info.field_name,
                "شناسه",
            ),
        )

    @field_validator("status")
    @classmethod
    def validate_status(
        cls,
        value: str,
    ) -> str:
        return _normalize_status(value)

    @field_validator("planned_departure_time")
    @classmethod
    def validate_planned_departure_time(
        cls,
        value: datetime,
    ) -> datetime:
        return _normalize_utc_datetime(value)

    @model_validator(mode="after")
    def validate_capacity_configuration(self):
        _validate_capacity_rules(
            seated_capacity=self.seated_capacity,
            standing_capacity=self.standing_capacity,
            allow_standing=self.allow_standing,
        )
        return self


class TripFromScheduleCreate(BaseModel):
    university_id: int
    schedule_id: int

    trip_date: date

    driver_id: int | None = None
    vehicle_id: int | None = None

    seated_capacity: int | None = Field(
        default=None,
        gt=0,
    )

    standing_capacity: int | None = Field(
        default=None,
        ge=0,
    )

    allow_standing: bool = False
    is_active: bool = True

    @field_validator(
        "university_id",
        "schedule_id",
    )
    @classmethod
    def validate_required_ids(
        cls,
        value: int,
        info,
    ) -> int:
        field_names = {
            "university_id": "شناسه دانشگاه",
            "schedule_id": "شناسه برنامه زمانی",
        }

        return _validate_positive_id(
            value,
            field_names.get(
                info.field_name,
                "شناسه",
            ),
        )

    @field_validator(
        "driver_id",
        "vehicle_id",
    )
    @classmethod
    def validate_optional_ids(
        cls,
        value: int | None,
        info,
    ) -> int | None:
        if value is None:
            return value

        field_names = {
            "driver_id": "شناسه راننده",
            "vehicle_id": "شناسه خودرو",
        }

        return _validate_positive_id(
            value,
            field_names.get(
                info.field_name,
                "شناسه",
            ),
        )

    @model_validator(mode="after")
    def validate_capacity_configuration(self):
        _validate_capacity_rules(
            seated_capacity=self.seated_capacity,
            standing_capacity=self.standing_capacity,
            allow_standing=self.allow_standing,
        )
        return self


class DailyTripGenerationRequest(BaseModel):
    university_id: int
    trip_date: date

    @field_validator("university_id")
    @classmethod
    def validate_university_id(
        cls,
        value: int,
    ) -> int:
        return _validate_positive_id(
            value,
            "شناسه دانشگاه",
        )


class TripAssignmentUpdate(BaseModel):
    driver_id: int | None = None
    vehicle_id: int | None = None

    @field_validator(
        "driver_id",
        "vehicle_id",
    )
    @classmethod
    def validate_resource_ids(
        cls,
        value: int | None,
        info,
    ) -> int | None:
        if value is None:
            return value

        field_names = {
            "driver_id": "شناسه راننده",
            "vehicle_id": "شناسه خودرو",
        }

        return _validate_positive_id(
            value,
            field_names.get(
                info.field_name,
                "شناسه",
            ),
        )


class TripResponse(BaseModel):
    id: int
    university_id: int
    service_id: int
    schedule_id: int | None

    driver_id: int | None
    vehicle_id: int | None

    seated_capacity: int | None
    standing_capacity: int | None
    allow_standing: bool

    trip_date: date

    planned_departure_time: datetime
    actual_departure_time: datetime | None
    actual_arrival_time: datetime | None

    status: str
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True,
    )


class TripStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(
        cls,
        value: str,
    ) -> str:
        return _normalize_status(value)