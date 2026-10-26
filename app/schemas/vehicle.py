from pydantic import BaseModel, Field


class VehicleCreate(BaseModel):
    university_id: int

    driver_id: int | None = None

    plate_number: str = Field(
        min_length=1,
        max_length=20,
    )

    vehicle_type: str = Field(
        min_length=1,
        max_length=50,
    )

    capacity: int = Field(
        gt=0,
    )

    is_active: bool = True


class VehicleResponse(BaseModel):
    id: int
    university_id: int
    driver_id: int | None
    plate_number: str
    vehicle_type: str
    capacity: int
    is_active: bool

    class Config:
        from_attributes = True
