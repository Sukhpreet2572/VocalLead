from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

class RequirementsSnapshot(BaseModel):
    location: str | None = None
    configuration: str | None = None
    max_budget_inr: int | None = None
    timeline_months: int | None = None
    property_type: str | None = None
    ready_to_move: bool | None = None

class ConversationSnapshot(BaseModel):
    main_objective: str | None = None
    discussed_property_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    sentiment: str = "UNKNOWN"

class LeadSnapshot(BaseModel):
    score: int
    classification: str
    components: dict
    purchase_intent: str | None = None
    recommended_follow_up: str

class BusinessSnapshot(BaseModel):
    proposal_status: str | None = None
    appointment_status: str | None = None
    appointment_id: str | None = None
    calendar_sync_status: str | None = None
    crm_lifecycle_status: str | None = None
    crm_sync_status: str | None = None

class SummaryMetadata(BaseModel):
    interaction_type: Literal["VOICE", "LOCAL_DEMO"]
    generation_method: Literal["LLM", "DETERMINISTIC"]
    model_id: str | None = None
    generated_at: datetime
    data_completeness: Literal["LIMITED", "PARTIAL", "SUBSTANTIAL"]
    limitations: list[str] = Field(default_factory=list)

class StructuredSummary(BaseModel):
    requirements: RequirementsSnapshot
    conversation: ConversationSnapshot
    lead: LeadSnapshot
    business: BusinessSnapshot
    metadata: SummaryMetadata
    summary_text: str = Field(min_length=1, max_length=3000)

class NarrativeOutput(BaseModel):
    summary_text: str = Field(min_length=1, max_length=3000)
