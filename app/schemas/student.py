from pydantic import BaseModel, Field, field_validator


ALLOWED_GENDERS = {
    "male",
    "female",
}


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

    gender: str

    national_id: str | None = Field(
        default=None,
        max_length=20
    )

    phone: str | None = Field(
        default=None,
        max_length=20
    )

    is_active: bool = True

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_GENDERS:
            raise ValueError(
                "جنسیت باید male یا female باشد"
            )

        return value


class StudentResponse(BaseModel):
    id: int
    university_id: int
    student_number: str
    first_name: str
    last_name: str
    gender: str
    national_id: str | None
    phone: str | None
    is_active: bool

    class Config:
        from_attributes = True