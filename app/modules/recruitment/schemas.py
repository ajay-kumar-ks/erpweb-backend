from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ──────────────────────────────────────────────
# Pipeline Template Schemas
# ──────────────────────────────────────────────

class PipelineTemplateCreate(BaseModel):
    department_id: int
    stages: list[str]


class PipelineTemplateUpdate(BaseModel):
    stages: Optional[list[str]] = None


class PipelineTemplateResponse(BaseModel):
    id: int
    department_id: int
    stages: list[str]
    department_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Candidate Schemas
# ──────────────────────────────────────────────

class CandidateCreate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    department_id: int  # Required — pipeline stages are determined from the department
    experience_years: float = 0
    notes: Optional[str] = None
    resume_url: Optional[str] = None


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    experience_years: Optional[float] = None
    notes: Optional[str] = None
    resume_url: Optional[str] = None


class CandidateResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    experience_years: float
    current_stage: str
    pipeline_stages: Optional[list[str]] = None
    status: str
    converted_to_employee: bool
    resume_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MoveStageRequest(BaseModel):
    target_stage: str  # free-form string matching a stage in the pipeline


class ConvertToEmployeeRequest(BaseModel):
    username: str
    password: str
