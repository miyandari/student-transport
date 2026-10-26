from pydantic import BaseModel, Field


class StudentCreate(BaseModel):
    university_id: int

    student_number: str = Field(
        min_length=1,
        max_length=50
    )

    first_name: str = Field(
        min_length=1,
        max_length=100
    )

    last_name: str = Field(
        min_length=1,
        max_length=100
    )

    national_id: str | None = Field(
        default=None,
        max_length=20
    )

    phone: str | None = Field(
        default=None,
        max_length=20
    )

    is_active: bool = True


class StudentResponse(BaseModel):
    id: int
    university_id: int
    student_number: str
    first_name: str
    last_name: str
    national_id: str | None
    phone: str | None
    is_active: bool

    class Config:
        from_attributes = True