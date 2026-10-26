from datetime import date

from pydantic import BaseModel, ConfigDict


class ContractDriverCreate(BaseModel):
    contract_id: int
    driver_id: int
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True


class ContractDriverResponse(BaseModel):
    id: int
    contract_id: int
    driver_id: int
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )