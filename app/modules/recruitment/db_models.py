from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.base import BaseModel


# ──────────────────────────────────────────────
# Pipeline Template — configurable stages per Department
# ──────────────────────────────────────────────

class PipelineTemplate(BaseModel):
    """
    Each Department can have one pipeline template defining its recruitment stages.
    Stages are stored as an ordered JSON array of strings, e.g.:
    ["Applied", "Screening", "Technical Test", "Technical Interview", "HR Interview", "Selected", "Onboarded"]
    """
    __tablename__ = "pipeline_templates"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), unique=True, nullable=False)
    stages = Column(JSON, nullable=False)  # ordered list of stage names

    department = relationship("Department")

    def __repr__(self):
        return f"<PipelineTemplate(id={self.id}, department_id={self.department_id}, stages={len(self.stages)})>"


# ──────────────────────────────────────────────
# Candidate
# ──────────────────────────────────────────────

class Candidate(BaseModel):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)

    # FK to Department (the department the candidate applied for)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    experience_years = Column(Float, default=0, nullable=False)

    # Current stage is a free-form string (not enum) to support dynamic pipelines
    current_stage = Column(String(100), default="Applied", nullable=False)

    # Snapshot of the candidate's pipeline stages at time of creation
    pipeline_stages = Column(JSON, nullable=True)

    status = Column(String(50), default="active", nullable=False)  # active, rejected, onboarded, converted
    converted_to_employee = Column(Boolean, default=False, nullable=False)

    resume_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)

    department = relationship("Department")

    def __repr__(self):
        return f"<Candidate(id={self.id}, name={self.full_name}, stage={self.current_stage})>"


# ──────────────────────────────────────────────
# Stage helpers
# ──────────────────────────────────────────────

def get_stage_index(candidate: Candidate, stage_name: str) -> int:
    """Get the index of a stage name in the candidate's pipeline. Returns -1 if not found."""
    stages = candidate.pipeline_stages or []
    try:
        return stages.index(stage_name)
    except ValueError:
        return -1


def can_move_to_stage(candidate: Candidate, target_stage: str) -> bool:
    """
    Allow forward progression within the candidate's pipeline, or jump to Rejected.
    Terminal stages (Onboarded, Rejected) cannot be left.
    """
    stages = candidate.pipeline_stages or []

    # Rejected is a special terminal state — can always move TO it (unless already terminal)
    if target_stage == "Rejected":
        return candidate.current_stage not in ("Rejected", "Onboarded", "Converted")

    # Can't move from terminal states
    if candidate.current_stage in ("Rejected", "Onboarded", "Converted"):
        return False

    try:
        current_idx = stages.index(candidate.current_stage)
        target_idx = stages.index(target_stage)
        return target_idx >= current_idx
    except ValueError:
        return False


def is_final_pipeline_stage(candidate: Candidate) -> bool:
    """Check if the candidate is on the last non-special stage before Onboarded."""
    stages = candidate.pipeline_stages or []
    if not stages:
        return False
    return candidate.current_stage == stages[-1] if stages else False


# ──────────────────────────────────────────────
# Default pipeline template
# ──────────────────────────────────────────────

DEFAULT_PIPELINE_STAGES = [
    "Applied",
    "Screening",
    "Interview",
    "HR Interview",
    "Selected",
    "Onboarded",
]
