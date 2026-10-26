from pydantic import BaseModel, Field


class DriverCreate(BaseModel):
    university_id: int

    transport_company_id: int | None = None

    first_name: str = Field(
        min_length=1,
        max_length=100,
    )

    last_name: str = Field(
        min_length=1,
        max_length=100,
    )

    national_id: str | None = Field(
        default=None,
        max_length=20,
    )

    phone: str = Field(
        min_length=1,
        max_length=20,
    )

    license_number: str | None = Field(
        default=None,
        max_length=50,
    )

    is_active: bool = True


class DriverResponse(BaseModel):
    id: int
    university_id: int
    transport_company_id: int | None

    first_name: str
    last_name: str

    national_id: str | None
    phone: str

    license_number: str | None

    is_active: bool

    class Config:
        from_attributes = True
