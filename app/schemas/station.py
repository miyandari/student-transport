from pydantic import BaseModel, Field


class StationCreate(BaseModel):
    university_id: int

    name: str = Field(
        min_length=1,
        max_length=200
    )

    address: str | None = Field(
        default=None,
        max_length=500
    )

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90
    )

    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180
    )

    is_active: bool = True


class StationResponse(BaseModel):
    id: int
    university_id: int

    name: str
    address: str | None

    latitude: float | None
    longitude: float | None

    is_active: bool

    class Config:
        from_attributes = True