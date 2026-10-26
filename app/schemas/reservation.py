from datetime import datetime

from pydantic import BaseModel, Field, field_validator


ALLOWED_RESERVATION_STATUSES = {
    "active",
    "cancelled",
}


class ReservationCreate(BaseModel):
    trip_id: int
    student_id: int
    is_standing: bool = False


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