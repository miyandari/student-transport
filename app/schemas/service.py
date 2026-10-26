from pydantic import BaseModel, Field


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

    is_active: bool = True


class ServiceResponse(BaseModel):
    id: int
    university_id: int
    route_id: int
    contract_id: int | None
    name: str
    code: str
    service_type: str
    is_active: bool

    class Config:
        from_attributes = True
