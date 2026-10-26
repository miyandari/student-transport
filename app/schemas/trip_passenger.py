from datetime import datetime

from pydantic import BaseModel, Field, field_validator


ALLOWED_BOARDING_METHODS = {
    "qr",
    "manual",
    "driver",
}


class TripPassengerCreate(BaseModel):
    trip_id: int
    student_id: int
    boarding_method: str = Field(min_length=1, max_length=50)
    is_standing: bool = False
    boarding_station_id: int | None = None
    alighting_station_id: int | None = None

    @field_validator("boarding_method")
    @classmethod
    def validate_boarding_method(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_BOARDING_METHODS:
            raise ValueError(
                "روش سوارشدن نامعتبر است"
            )

        return value


class TripPassengerResponse(BaseModel):
    id: int
    trip_id: int
    student_id: int
    boarding_time: datetime | None
    boarding_station_id: int | None
    alighting_time: datetime | None
    alighting_station_id: int | None
    boarding_method: str
    is_standing: bool

    class Config:
        from_attributes = True


class TripPassengerBoardRequest(BaseModel):
    student_id: int
    boarding_method: str = Field(
        default="manual",
        min_length=1,
        max_length=50,
    )
    is_standing: bool = False
    boarding_station_id: int | None = None

    @field_validator("boarding_method")
    @classmethod
    def validate_boarding_method(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_BOARDING_METHODS:
            raise ValueError(
                "روش سوارشدن نامعتبر است"
            )

        return value
    

class TripPassengerQRBoardRequest(BaseModel):
    qr_token: str = Field(
        min_length=20,
        max_length=100,
    )
    is_standing: bool = False
    boarding_station_id: int | None = None
  