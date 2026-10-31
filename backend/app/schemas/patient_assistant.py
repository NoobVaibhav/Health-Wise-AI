from pydantic import BaseModel, Field, field_validator

from app.services.patient_assistant import MAX_MESSAGE
from app.utils.validators import PositiveId


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    conversation_id: PositiveId | None = None
    language: str = "en"
    ai_consent: bool = False                  # the patient agreed that wording help from an outside AI service may be used

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Please type a question.")
        return v
