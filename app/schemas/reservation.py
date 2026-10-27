from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from pydantic.aliases import AliasChoices


ALLOWED_RESERVATION_STATUSES = {
    "active",
    "cancelled",
}


class ReservationCreate(BaseModel):
    trip_id: int
    student_id: int

    is_standing: bool = Field(
        default=False,
        validation_alias=AliasChoices("reservation_type", "is_standing"),
    )

    @field_validator("is_standing", mode="before")
    @classmethod
    def validate_reservation_type(cls, value):
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        value = str(value).strip().lower()

        if value == "seated":
            return False

        if value == "standing":
            return True

        raise ValueError(
            "نوع رزرو باید یکی از مقادیر seated یا standing باشد"
        )


class ReservationResponse(BaseModel):
    id: int
    trip_id: int
    student_id: int
    reservation_time: datetime
    status: str
    is_standing: bool

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_RESERVATION_STATUSES:
            raise ValueError("وضعیت رزرو نامعتبر است")

        return value

    class Config:
        from_attributes = True