from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int

    user_id: int | None = None
    university_id: int | None = None
    transport_company_id: int | None = None

    action: str
    entity_type: str
    entity_id: int | None = None

    description: str | None = None

    old_values: dict | None = None
    new_values: dict | None = None

    ip_address: str | None = None
    user_agent: str | None = None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )