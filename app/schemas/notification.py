from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    university_id: int | None = None
    transport_company_id: int | None = None
    notification_type: str
    title: str
    message: str
    data: dict | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime