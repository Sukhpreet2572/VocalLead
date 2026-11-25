from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, pattern=r"^\+?[0-9]{10,15}$")
    email: str | None = Field(None, max_length=254)
    preferred_language: Literal["en", "hi", "hinglish"] | None = None
    contact_consent: bool | None = None
    location: str | None = Field(None, max_length=100)
    property_type: str | None = Field(None, max_length=30)
    configuration: str | None = Field(None, pattern=r"^[1-6] BHK$")
    min_budget_inr: int | None = Field(None, ge=100_000, le=2_000_000_000)
    max_budget_inr: int | None = Field(None, ge=100_000, le=2_000_000_000)
    timeline_months: int | None = Field(None, ge=0, le=120)
    purchase_intent: Literal["STRONG", "EXPLORING", "NOT_INTERESTED"] | None = None
    ready_to_move: bool | None = None
    site_visit_interest: bool | None = None
    interested_property_ids: list[str] | None = Field(None, max_length=20)

    @field_validator("email")
    @classmethod
    def email_shape(cls, value: str | None) -> str | None:
        if value and ("@" not in value or "." not in value.split("@")[-1]):
            raise ValueError("Invalid email address")
        return value

class MessageInput(BaseModel):
    message: str = Field(min_length=3, max_length=1000)
