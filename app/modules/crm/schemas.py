from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional, Any
from datetime import datetime


# Custom Field Schema
class CustomFieldSchema(BaseModel):
    label: str
    value: Any


# Tag Schemas
class TagBaseSchema(BaseModel):
    name: str
    color: Optional[str] = "#6366f1"


class TagSchema(TagBaseSchema):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Activity Schemas
class ActivityBaseSchema(BaseModel):
    activity_type: str  # note, call, email, meeting, file
    title: str
    description: Optional[str] = None
    follow_up_date: Optional[datetime] = None
    meta_data: Optional[dict] = {}


class ActivityCreateSchema(ActivityBaseSchema):
    pass


class ActivitySchema(ActivityBaseSchema):
    id: str
    contact_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Contact Schemas
class ContactBaseSchema(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    avatar_url: Optional[str] = None
    custom_fields: Optional[List[Any]] = None
    source: Optional[str] = None

    @field_validator("email", "phone")
    @classmethod
    def validate_contact_info(cls, v, info):
        """Ensure at least email or phone is provided"""
        # This will be checked at the create level
        return v


class ContactCreateSchema(ContactBaseSchema):
    tags: Optional[List[str]] = []  # tag names to link


class ContactUpdateSchema(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    avatar_url: Optional[str] = None
    custom_fields: Optional[List[Any]] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None  # tag names
    status: Optional[str] = None


class ContactSchema(ContactBaseSchema):
    id: str
    status: str
    tags: List[TagSchema] = []
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContactDetailSchema(ContactSchema):
    activities: List[ActivitySchema] = []


# Pipeline / Phase / Lead Schemas (Phase 2)
class PhaseSchema(BaseModel):
    id: str
    pipeline_id: str
    name: str
    color: Optional[str] = "#6b7280"
    position: Optional[int] = 0
    is_terminal: Optional[bool] = False
    creates_client: Optional[bool] = False

    class Config:
        from_attributes = True


class PipelineSchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None

    class Config:
        from_attributes = True


class PipelineCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None


class PipelineUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None


class PhaseCreateSchema(BaseModel):
    name: str
    color: Optional[str] = "#6b7280"
    position: Optional[int] = 0
    is_terminal: Optional[bool] = False
    creates_client: Optional[bool] = False


class PhaseUpdateSchema(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None
    is_terminal: Optional[bool] = None
    creates_client: Optional[bool] = None


# ── Pipeline Assignment Schemas ──

class DepartmentAssignmentConfig(BaseModel):
    department_id: int
    department_name: str
    assignment_mode: str = "round_robin"  # round_robin, self_assign, individual
    selected_members: list[int] = []  # employee IDs for round robin
    individual_assignee_id: Optional[int] = None
    round_robin_index: int = 0


class PipelineAssignmentCreateSchema(BaseModel):
    departments_config: list[DepartmentAssignmentConfig] = []


class PipelineAssignmentUpdateSchema(BaseModel):
    departments_config: list[DepartmentAssignmentConfig]


class AssignToPipelineSchema(BaseModel):
    department_id: int
    assignment_mode: str  # round_robin, individual


class PipelineAssignmentSchema(BaseModel):
    id: str
    pipeline_id: str
    departments_config: list[DepartmentAssignmentConfig] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadBaseSchema(BaseModel):
    title: str
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    phase_id: Optional[str] = None
    value: Optional[int] = None
    expected_close_date: Optional[datetime] = None
    assignee: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    extra_data: Optional[dict] = {}


class LeadCreateSchema(LeadBaseSchema):
    pass


class LeadUpdateSchema(BaseModel):
    title: Optional[str] = None
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    phase_id: Optional[str] = None
    value: Optional[int] = None
    expected_close_date: Optional[datetime] = None
    assignee: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    extra_data: Optional[dict] = None


class LeadSchema(LeadBaseSchema):
    id: str
    created_at: datetime
    updated_at: datetime
    contact: Optional[ContactSchema] = None
    pipeline: Optional[PipelineSchema] = None
    phase: Optional[PhaseSchema] = None

    class Config:
        from_attributes = True


# ── AI Pipeline Insights Schemas (Phase 4) ──

class PipelineInsight(BaseModel):
    severity: str = "info"  # critical, warning, info, positive
    type: str = "insight"   # summary, risk, opportunity, bottleneck, recommendation, insight
    message: str
    details: Optional[str] = None  # AI-generated detailed explanation
    count: int = 0
    filter_query: Optional[str] = None  # e.g. "stalled" or "phase=phase_id"
    lead_ids: Optional[list[str]] = None  # related lead IDs for click-through
    action_label: Optional[str] = None  # e.g. "View stalled leads", "View hot leads"


class PipelineHealthSummary(BaseModel):
    score: int = 0  # 0-100 overall pipeline health
    total_value: int = 0
    lead_count: int = 0
    top_risk: Optional[str] = None
    top_opportunity: Optional[str] = None
    recommendation: Optional[str] = None


class PipelineInsightsResponse(BaseModel):
    insights: list[PipelineInsight] = []
    summary: Optional[PipelineHealthSummary] = None
    pipeline_id: str
    pipeline_name: str = ""


# ── AI Next-Best-Action Schemas (Phase 3) ──

class AINextActionRequest(BaseModel):
    lead_id: str


class AINextActionResponse(BaseModel):
    action: str
    description: str
    suggested_phase_id: Optional[str] = None
    urgency: str = "medium"  # high, medium, low


# ── AI Suggest Assignee Schemas (Phase 2) ──

class AISuggestAssigneeRequest(BaseModel):
    title: str = ""
    value: Optional[int] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    pipeline_id: str
    contact_company: Optional[str] = None


class AssigneeSuggestion(BaseModel):
    employee_id: int
    name: str
    confidence: int
    reason: str
    current_load: int


class AISuggestAssigneeResponse(BaseModel):
    suggestions: list[AssigneeSuggestion] = []


# ── CRM Chatbot Schemas (Phase 5) ──

class ChatbotMessage(BaseModel):
    role: str = "user"  # user, assistant
    content: str


class ChatbotRequest(BaseModel):
    message: str
    history: list[ChatbotMessage] = []


class ChatbotResponse(BaseModel):
    reply: str


# Merge Request Schema
class MergeContactsSchema(BaseModel):
    primary_id: str
    secondary_id: str
    keep_fields: Optional[dict] = {}  # which fields to keep from secondary


# Bulk Action Schema
class BulkActionSchema(BaseModel):
    contact_ids: List[str]
    action: str  # tag, assign, export, archive
    action_data: Optional[dict] = {}


# Client Schemas (Phase 4) ✅ 4.1
class ClientBaseSchema(BaseModel):
    contact_id: str
    lead_id: Optional[str] = None
    account_manager: Optional[str] = None
    tier: str = "Standard"  # Standard, Premium, VIP
    status: str = "Active"  # Active, Inactive, Churned
    renewal_date: Optional[datetime] = None
    subscription_value: Optional[int] = None
    pinned_notes: Optional[str] = None
    internal_tags: Optional[List[str]] = []


class ClientCreateSchema(BaseModel):
    contact_id: str
    lead_id: Optional[str] = None
    account_manager: Optional[str] = None
    tier: Optional[str] = "Standard"


class ClientUpdateSchema(BaseModel):
    account_manager: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None
    renewal_date: Optional[datetime] = None
    subscription_value: Optional[int] = None
    pinned_notes: Optional[str] = None
    internal_tags: Optional[List[str]] = None


class ClientSchema(ClientBaseSchema):
    id: str
    client_since: datetime
    activity_notes: List[Any] = []
    linked_projects: List[Any] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClientDetailSchema(ClientSchema):
    """Client with full contact information"""
    contact: Optional[ContactSchema] = None
