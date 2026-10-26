from pydantic import BaseModel, Field


class RouteCreate(BaseModel):
    university_id: int

    name: str = Field(
        min_length=1,
        max_length=200
    )

    code: str = Field(
        min_length=1,
        max_length=50
    )

    direction: str = Field(
        min_length=1,
        max_length=20
    )

    description: str | None = Field(
        default=None,
        max_length=1000
    )

    is_active: bool = True


class RouteResponse(BaseModel):
    id: int
    university_id: int
    name: str
    code: str
    direction: str
    description: str | None
    is_active: bool

    class Config:
        from_attributes = True