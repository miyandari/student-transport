from pydantic import BaseModel, Field


class UniversityCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=200
    )

    code: str = Field(
        min_length=1,
        max_length=50
    )

    is_active: bool = True


class UniversityResponse(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True