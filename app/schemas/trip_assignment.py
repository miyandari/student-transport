from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TripAssignmentCreate(BaseModel):
    trip_id: int

    driver_id: int | None = None
    vehicle_id: int | None = None

    assigned_by_user_id: int

    replaces_assignment_id: int | None = None

    assignment_type: str = "primary"

    reason: str | None = None

    start_at: datetime | None = None
    end_at: datetime | None = None

    is_active: bool = True


class TripAssignmentResponse(BaseModel):
    id: int

    trip_id: int

    driver_id: int | None = None
    vehicle_id: int | None = None

    assigned_by_user_id: int

    replaces_assignment_id: int | None = None

    assignment_type: str

    reason: str | None = None

    start_at: datetime | None = None
    end_at: datetime | None = None

    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )