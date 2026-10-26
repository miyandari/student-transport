from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class FeedbackCreate(BaseModel):
    trip_id: int
    student_id: int
    rating: int | None = Field(
        default=None,
        ge=1,
        le=5,
    )
    feedback_type: str = Field(
        min_length=1,
        max_length=50,
    )
    title: str | None = Field(
        default=None,
        max_length=200,
    )
    message: str | None = Field(
        default=None,
        max_length=5000,
    )

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "نوع بازخورد نمی‌تواند خالی باشد"
            )

        return value

    @field_validator("title")
    @classmethod
    def normalize_title(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value if value else None

    @field_validator("message")
    @classmethod
    def normalize_message(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value if value else None


class FeedbackResponse(BaseModel):
    id: int
    trip_id: int
    student_id: int
    rating: int | None
    feedback_type: str
    title: str | None
    message: str | None
    created_at: datetime
    is_resolved: bool

    class Config:
        from_attributes = True