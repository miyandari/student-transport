from pydantic import BaseModel, ConfigDict


class TransportCompanyCreate(BaseModel):
    name: str
    registration_number: str | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool = True


class TransportCompanyResponse(BaseModel):
    id: int
    name: str
    registration_number: str | None = None
    phone: str | None = None
    address: str | None = None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )


class TransportCompanyStatusUpdate(BaseModel):
    is_active: bool