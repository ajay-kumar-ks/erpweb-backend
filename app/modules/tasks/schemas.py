import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from enum import Enum


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Status(str, Enum):
    TODO = "TODO"
    ON_PROGRESS = "ON_PROGRESS"
    ON_HOLD = "ON_HOLD"
    ON_REVIEW = "ON_REVIEW"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: Priority = Priority.MEDIUM
    status: Status = Status.TODO
    reason_note: Optional[str] = None
    due_date: datetime
    proof_attachment: Optional[str] = None

    @model_validator(mode='after')
    def set_overdue_if_past_due(cls, values):
        if values.due_date < datetime.now(timezone.utc):
            values.status = Status.OVERDUE
        return values


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None
    reason_note: Optional[str] = None
    due_date: Optional[datetime] = None
    proof_attachment: Optional[str] = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    created_by: int
    priority: Priority
    status: Status
    reason_note: Optional[str] = None
    proof_attachment: Optional[str] = None
    due_date: datetime
    created_at: datetime
    updated_at: datetime

    # Employee details (populated at query time)
    assignee_name: Optional[str] = None
    assignee_email: Optional[str] = None
    assignee_department: Optional[str] = None
    assignee_designation: Optional[str] = None

    # Subtask / checklist progress (populated at query time)
    subtask_count: int = 0
    subtask_completed_count: int = 0

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Task Comment Schemas
# ──────────────────────────────────────────────


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    mentioned_user_ids: Optional[list[int]] = None


class TaskCommentResponse(BaseModel):
    id: int
    task_id: uuid.UUID
    user_id: int
    content: str
    created_at: datetime
    updated_at: datetime
    mentioned_user_ids: Optional[str] = None

    # User details (populated at query time)
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Task Activity Schemas
# ──────────────────────────────────────────────


class TaskActivityResponse(BaseModel):
    id: int
    task_id: uuid.UUID
    user_id: int
    action: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime

    # User details (populated at query time)
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Task Dependency Schemas
# ──────────────────────────────────────────────


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class TaskDependencyResponse(BaseModel):
    id: int
    task_id: uuid.UUID
    depends_on_task_id: uuid.UUID
    created_at: datetime

    # Details of the depended-on task (populated at query time)
    depends_on_title: Optional[str] = None
    depends_on_status: Optional[str] = None
    depends_on_priority: Optional[str] = None

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# SubTask / Checklist Schemas
# ──────────────────────────────────────────────


class SubTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class SubTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    completed: Optional[bool] = None


class SubTaskResponse(BaseModel):
    id: int
    task_id: uuid.UUID
    title: str
    completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_compat(cls, obj) -> "SubTaskResponse":
        """Convert the DB model (where completed is an int 0/1) to the Pydantic schema (bool)."""
        data = {
            "id": obj.id,
            "task_id": obj.task_id,
            "title": obj.title,
            "completed": bool(obj.completed),
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


# ──────────────────────────────────────────────
# Task Notification Schemas
# ──────────────────────────────────────────────


class TaskNotificationResponse(BaseModel):
    id: int
    user_id: int
    task_id: uuid.UUID
    type: str  # "mention" or "status_change"
    message: str
    actor_id: int
    read: bool
    created_at: datetime

    # Enriched fields
    actor_name: Optional[str] = None
    task_title: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_compat(cls, obj) -> "TaskNotificationResponse":
        data = {
            "id": obj.id,
            "user_id": obj.user_id,
            "task_id": obj.task_id,
            "type": obj.type,
            "message": obj.message,
            "actor_id": obj.actor_id,
            "read": bool(obj.read),
            "created_at": obj.created_at,
            "actor_name": getattr(obj, "actor_name", None),
            "task_title": getattr(obj, "task_title", None),
        }
        return cls(**data)
