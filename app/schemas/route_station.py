from pydantic import BaseModel, Field


class RouteStationCreate(BaseModel):
    route_id: int
    station_id: int

    stop_order: int = Field(
        ge=1
    )

    estimated_minutes_from_start: int | None = Field(
        default=None,
        ge=0
    )

    stop_duration_seconds: int | None = Field(
        default=None,
        ge=0
    )


class RouteStationResponse(BaseModel):
    id: int
    route_id: int
    station_id: int
    stop_order: int
    estimated_minutes_from_start: int | None
    stop_duration_seconds: int | None

    class Config:
        from_attributes = True