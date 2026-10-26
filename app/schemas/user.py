from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    id: int
    username: str

    first_name: str | None
    last_name: str | None
    phone: str | None

    role: str

    university_id: int | None
    transport_company_id: int | None
    student_id: int | None
    driver_id: int | None

    is_active: bool

    class Config:
        from_attributes = True


class ChangeMyPasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class ChangeUserPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserStatusResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    message: str
