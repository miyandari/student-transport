from pydantic import BaseModel, Field, field_validator


ALLOWED_GENDER_RESTRICTIONS = {
    "mixed",
    "male",
    "female",
}


class ServiceCreate(BaseModel):
    university_id: int
    route_id: int
    contract_id: int | None = None

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    code: str = Field(
        min_length=1,
        max_length=50,
    )

    service_type: str = Field(
        min_length=1,
        max_length=50,
    )

    gender_restriction: str = "mixed"

    is_active: bool = True

    @field_validator("gender_restriction")
    @classmethod
    def validate_gender_restriction(cls, value: str) -> str:
        value = value.strip().lower()

        if value not in ALLOWED_GENDER_RESTRICTIONS:
            raise ValueError(
                "محدودیت جنسیتی باید mixed، male یا female باشد"
            )

        return value


class ServiceResponse(BaseModel):
    id: int
    university_id: int
    route_id: int
    contract_id: int | None
    name: str
    code: str
    service_type: str
    gender_restriction: str
    is_active: bool

    class Config:
        from_attributes = True