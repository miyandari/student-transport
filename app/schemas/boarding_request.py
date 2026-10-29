from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BoardingRequestCreate(BaseModel):
    trip_id: int
    boarding_station_id: int | None = None
    is_standing: bool = False


class BoardingRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    student_id: int
    boarding_station_id: int | None = None
    is_standing: bool
    status: str
    requested_at: datetime
    responded_at: datetime | None = None
    responded_by_user_id: int | None = None
    rejection_reason: str | None = None


class BoardingRequestDecision(BaseModel):
    approved: bool
    rejection_reason: str | None = None