from datetime import date

from pydantic import BaseModel, ConfigDict


class ContractVehicleCreate(BaseModel):
    contract_id: int
    vehicle_id: int
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True


class ContractVehicleResponse(BaseModel):
    id: int
    contract_id: int
    vehicle_id: int
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )