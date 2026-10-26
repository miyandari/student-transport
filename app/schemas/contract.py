from datetime import date

from pydantic import BaseModel, Field


class ContractCreate(BaseModel):
    university_id: int

    transport_company_id: int

    contract_number: str = Field(
        min_length=1,
        max_length=100
    )

    start_date: date
    end_date: date

    contract_amount: int | None = Field(
        default=None,
        ge=0
    )

    description: str | None = Field(
        default=None,
        max_length=1000
    )

    is_active: bool = True


class ContractResponse(BaseModel):
    id: int

    university_id: int
    transport_company_id: int

    contract_number: str

    start_date: date
    end_date: date

    contract_amount: int | None
    description: str | None

    is_active: bool

    class Config:
        from_attributes = True