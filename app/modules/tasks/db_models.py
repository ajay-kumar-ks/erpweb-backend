import uuid
from enum import Enum
from sqlalchemy import Column, String, Text, Integer, DateTime, Enum as SqlEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import BaseModel


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


class Task(BaseModel):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    assignee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    priority = Column(SqlEnum(Priority), nullable=False, default=Priority.MEDIUM)
    status = Column(SqlEnum(Status), nullable=False, default=Status.TODO)
    reason_note = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=False)
    proof_attachment = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Task(id={self.id}, title={self.title}, status={self.status}, priority={self.priority})>"


class TaskComment(BaseModel):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    content = Column(Text, nullable=False)
    mentioned_user_ids = Column(Text, nullable=True)  # JSON array of user IDs e.g. "[1, 3, 7]"

    def __repr__(self):
        return f"<TaskComment(id={self.id}, task_id={self.task_id}, user_id={self.user_id})>"


class TaskActivity(BaseModel):
    """Stores an audit trail entry for task changes."""
    __tablename__ = "task_activities"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # e.g. created, updated, status_changed, commented, deleted
    field_name = Column(String(50), nullable=True)  # e.g. title, status, priority, assignee, due_date
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    def __repr__(self):
        return f"<TaskActivity(id={self.id}, task_id={self.task_id}, action={self.action})>"


class TaskDependency(BaseModel):
    """Tracks 'depends on' relationships between tasks.

    If task A depends on task B:
      - task_id = A (the task that is waiting)
      - depends_on_task_id = B (the task that blocks)
    """
    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    depends_on_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    def __repr__(self):
        return f"<TaskDependency(id={self.id}, task_id={self.task_id}, depends_on={self.depends_on_task_id})>"


class SubTask(BaseModel):
    """A sub-task / checklist item within a parent task."""
    __tablename__ = "sub_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    completed = Column(Integer, default=0)  # 0 = not completed, 1 = completed

    def __repr__(self):
        return f"<SubTask(id={self.id}, task_id={self.task_id}, title={self.title}, completed={self.completed})>"


class TaskNotification(BaseModel):
    """Stores notifications for users about task events (mentions, status changes)."""
    __tablename__ = "task_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # "mention", "status_change"
    message = Column(Text, nullable=False)
    actor_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    read = Column(Integer, default=0)  # 0 = unread, 1 = read

    def __repr__(self):
        return f"<TaskNotification(id={self.id}, user_id={self.user_id}, type={self.type}, read={self.read})>"
