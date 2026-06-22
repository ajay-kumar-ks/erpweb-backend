import uuid
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.event_bus import event_bus
from app.modules.auth.models import User
from app.modules.auth.routers import get_current_user
from app.modules.tasks.crud import (
    create_task, get_tasks, get_task, update_task, delete_task,
    log_activity, get_activities_for_task,
    create_dependency, get_dependencies_for_task, delete_dependency,
)
from app.modules.tasks.schemas import (
    TaskCreate, TaskUpdate, TaskResponse,
    TaskCommentCreate, TaskCommentResponse,
    TaskActivityResponse,
    TaskDependencyCreate, TaskDependencyResponse,
    SubTaskCreate, SubTaskUpdate, SubTaskResponse,
    Priority, Status,
)
from app.modules.tasks.db_models import Task, TaskActivity, TaskDependency, SubTask

# Define the status progression order (higher = later in workflow)
STATUS_ORDER = {
    Status.TODO: 0,
    Status.ON_PROGRESS: 1,
    Status.ON_HOLD: 2,
    Status.ON_REVIEW: 3,
    Status.COMPLETED: 4,
    Status.OVERDUE: 5,
}

router = APIRouter()


def _get_employee_by_user_id(db: Session, user_id: int):
    """Look up an employee record by the auth user's ID."""
    try:
        from app.modules.hr.db_models import Employee
        return db.query(Employee).filter(Employee.user_id == user_id).first()
    except Exception:
        return None


def _get_employee_id(db: Session, current_user: User) -> Optional[int]:
    """Get the employee ID for the current user, if they have an employee record."""
    employee = _get_employee_by_user_id(db, current_user.id)
    return employee.id if employee else None


def _notify_task_assignee(db: Session, task_id: uuid.UUID, assignee_employee_id: int, message: str, type_: str, actor_id: int):
    """Helper: create a notification for the auth user linked to an employee/assignee.
    Returns True if notification was created, False otherwise."""
    try:
        from app.modules.hr.db_models import Employee
        employee = db.query(Employee).filter(Employee.id == assignee_employee_id).first()
        if employee and employee.user_id:
            from app.modules.tasks.crud import create_notification
            create_notification(
                db=db,
                user_id=employee.user_id,
                task_id=task_id,
                type_=type_,
                message=message,
                actor_id=actor_id,
            )
            return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to create notification: %s", e)
    return False


# ──────────────────────────────────────────────
# Employees — fetch from HR module for assignee dropdown
# ──────────────────────────────────────────────


@router.get("/employees", response_model=list[dict])
async def list_employees(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return employees from the HR module for the assignee dropdown.

    Queries the HR employees table directly, joining with users and departments.
    All authenticated users can access this (for dropdown rendering).
    """
    try:
        from app.modules.hr.db_models import Employee, EmployeeStatus
        from app.modules.auth.db_models import User as UserDB

        query = (
            db.query(Employee)
            .join(UserDB, Employee.user_id == UserDB.id)
            .options(joinedload(Employee.user), joinedload(Employee.department), joinedload(Employee.role))
            .filter(Employee.status == EmployeeStatus.ACTIVE)
        )

        if search:
            query = query.filter(
                UserDB.full_name.ilike(f"%{search}%")
            )

        employees = query.order_by(UserDB.full_name).all()

        return [
            {
                "id": emp.id,
                "user_id": emp.user_id,
                "employee_code": emp.employee_code,
                "name": emp.user.full_name if emp.user else None,
                "email": emp.user.email if emp.user else None,
                "department": emp.department.name if emp.department else None,
                "department_id": emp.department_id,
                "designation": emp.role.name if emp.role else None,
                "role_id": emp.role_id,
                "status": emp.status.value if emp.status else None,
            }
            for emp in employees
        ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to query HR employees table, falling back to event-bus cache: %s", e
        )
        # Fall back to the deprecated event-bus cache if HR tables don't exist
        from app.modules.tasks.event_handlers import get_employees as get_cached_employees
        return get_cached_employees()


# ──────────────────────────────────────────────
# User search for @mention autocomplete
# ──────────────────────────────────────────────


@router.get("/users/search")
async def search_users(
    q: str = Query("", min_length=1, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search auth users by name or email for @mention autocomplete."""
    try:
        from app.modules.auth.db_models import User as UserDB

        query = db.query(UserDB).filter(
            UserDB.full_name.ilike(f"%{q}%")
        ).order_by(UserDB.full_name).limit(10)

        users = query.all()
        return [
            {
                "id": u.id,
                "name": u.full_name or u.username,
                "email": u.email,
            }
            for u in users
        ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to search users: %s", e)
        return []


# ══════════════════════════════════════════════
# Task Notification Endpoints
# ══════════════════════════════════════════════


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return notifications for the current user."""
    from app.modules.tasks.crud import get_notifications_for_user, get_unread_notification_count
    from app.modules.tasks.schemas import TaskNotificationResponse

    notifications = get_notifications_for_user(db, current_user.id, unread_only=unread_only)
    return [TaskNotificationResponse.from_orm_compat(n) for n in notifications]


@router.get("/notifications/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the number of unread notifications for the current user."""
    from app.modules.tasks.crud import get_unread_notification_count
    count = get_unread_notification_count(db, current_user.id)
    return {"count": count}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    from app.modules.tasks.crud import mark_notification_read
    updated = mark_notification_read(db, notification_id, current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return {"status": "ok"}


@router.post("/notifications/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all unread notifications for the current user as read."""
    from app.modules.tasks.crud import mark_all_notifications_read
    count = mark_all_notifications_read(db, current_user.id)
    return {"status": "ok", "marked_read": count}


# ──────────────────────────────────────────────
# Task CRUD
# ──────────────────────────────────────────────


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    status_filter: Optional[Status] = Query(None, alias="status"),
    priority: Optional[Priority] = Query(None),
    assignee_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks.

    Admins see all tasks (with optional filters).
    Non-admin employees see only tasks assigned to them.
    """
    # Auto-filter for non-admin users
    employee_id = None
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None:
            # User has no employee record — return empty
            return []

    tasks = get_tasks(
        db,
        status=status_filter,
        priority=priority,
        assignee_id=assignee_id,
        search=search,
        employee_id=employee_id,
    )
    return tasks


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_new_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create tasks",
        )

    task = create_task(db, task_data, created_by=current_user.id)

    # Log activity
    log_activity(db, task.id, current_user.id, "created", "task", None, task.title)

    event_bus.publish("task.created", {
        "task_id": str(task.id),
        "title": task.title,
        "assignee_id": task.assignee_id,
        "due_date": task.due_date.isoformat(),
    })

    # Notify the assignee when a task is assigned to them
    if task.assignee_id:
        current_user_name = current_user.full_name or current_user.username
        _notify_task_assignee(
            db=db,
            task_id=task.id,
            assignee_employee_id=task.assignee_id,
            type_="task_assigned",
            message=f"{current_user_name} assigned you a new task: '{task.title}'.",
            actor_id=current_user.id,
        )

    return task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a single task by ID.

    Employees can only access tasks assigned to them.
    """
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Non-admin users can only view their own tasks
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view tasks assigned to you",
            )

    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_by_id(
    task_id: uuid.UUID,
    update_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a task.

    Admins can update any field.
    Assignee employees can only update status, reason_note, and proof_attachment.
    """
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Permission checks
    employee_id = _get_employee_id(db, current_user)
    is_assignee = employee_id is not None and task.assignee_id == employee_id

    if not current_user.is_admin and not is_assignee:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assignee or an admin can update this task",
        )

    # Non-admin employees can only change status, reason_note, and proof_attachment
    if not current_user.is_admin:
        allowed_fields = {"status", "reason_note", "proof_attachment"}
        update_fields = set(update_data.model_dump(exclude_unset=True).keys())
        disallowed = update_fields - allowed_fields
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Employees can only update status, reason_note, and proof_attachment. Cannot update: {', '.join(sorted(disallowed))}",
            )

    # Validate status transitions
    if update_data.status is not None and update_data.status != task.status:
        # COMPLETED can only be reached from ON_REVIEW (must go through review)
        if update_data.status == Status.COMPLETED and task.status != Status.ON_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot move directly to Completed from {task.status.value}. Tasks must go through On Review first.",
            )

        current_order = STATUS_ORDER.get(task.status, -1)
        new_order = STATUS_ORDER.get(update_data.status, -1)

        # Allowed backward transitions:
        #   OVERDUE  → ON_REVIEW    (overdue task completed, send for review)
        #   ON_HOLD  → ON_PROGRESS  (resume a held task)
        #   ON_REVIEW → TODO        (admin rejects review, sends back to todo)
        #   COMPLETED → ON_REVIEW   (admin reopens completed task for review)
        is_allowed_backward = (
            (task.status == Status.OVERDUE and update_data.status == Status.ON_REVIEW)
            or (task.status == Status.ON_HOLD and update_data.status == Status.ON_PROGRESS)
            or (task.status == Status.ON_REVIEW and update_data.status == Status.TODO and current_user.is_admin)
            or (task.status == Status.COMPLETED and update_data.status == Status.ON_REVIEW and current_user.is_admin)
        )

        if new_order <= current_order and not is_allowed_backward:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot move from {task.status.value} back to {update_data.status.value}. Status can only move forward.",
            )

    # Cannot manually set to OVERDUE (only the auto-scheduler can)
    if update_data.status is not None and update_data.status == Status.OVERDUE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Overdue status is automatically assigned by the system when a task's deadline passes.",
        )

    # Require proof_attachment only when moving to COMPLETED
    if update_data.status is not None and update_data.status == Status.COMPLETED:
        if not update_data.proof_attachment or not update_data.proof_attachment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Proof attachment is required when marking a task as completed",
            )

    # Save old state for activity logging
    old_status = task.status
    old_assignee = task.assignee_id
    old_priority = task.priority
    old_title = task.title
    old_description = task.description
    old_due_date = task.due_date
    old_reason_note = task.reason_note
    old_proof_attachment = task.proof_attachment

    updated = update_task(db, task_id, update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Log activity for each changed field
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, new_val in update_dict.items():
        if field == 'status':
            old_str = old_status.value if old_status else None
            new_str = new_val.value if new_val else None
            if old_str != new_str:
                log_activity(db, task_id, current_user.id, "status_changed", "status", old_str, new_str)
        elif field == 'assignee_id':
            if old_assignee != new_val:
                log_activity(db, task_id, current_user.id, "updated", "assignee", str(old_assignee) if old_assignee else "Unassigned", str(new_val) if new_val else "Unassigned")
        elif field == 'priority':
            old_str = old_priority.value if old_priority else None
            new_str = new_val.value if new_val else None
            if old_str != new_str:
                log_activity(db, task_id, current_user.id, "updated", "priority", old_str, new_str)
        elif field == 'title':
            if str(old_title) != str(new_val):
                log_activity(db, task_id, current_user.id, "updated", "title", old_title, new_val)
        elif field == 'description':
            if str(old_description) != str(new_val):
                log_activity(db, task_id, current_user.id, "updated", "description", old_description or "(empty)", new_val or "(empty)")
        elif field == 'due_date':
            old_str = old_due_date.isoformat() if old_due_date else None
            new_str = new_val.isoformat() if hasattr(new_val, 'isoformat') else str(new_val)
            if old_str != new_str:
                log_activity(db, task_id, current_user.id, "updated", "due date", old_str, new_str)
        elif field == 'reason_note':
            if str(old_reason_note) != str(new_val):
                log_activity(db, task_id, current_user.id, "updated", "reason note", old_reason_note or "(empty)", new_val or "(empty)")
        elif field == 'proof_attachment':
            if str(old_proof_attachment) != str(new_val):
                log_activity(db, task_id, current_user.id, "updated", "proof", old_proof_attachment or None, new_val or None)

    # Publish status change event if status changed
    if update_data.status is not None and update_data.status != old_status:
        event_bus.publish("task.status_changed", {
            "task_id": str(task_id),
            "old_status": old_status.value,
            "new_status": update_data.status.value,
            "reason_note": update_data.reason_note,
        })

        if update_data.status == Status.COMPLETED:
            event_bus.publish("task.completed", {
                "task_id": str(task_id),
                "assignee_id": task.assignee_id,
            })

        # Notify the assignee about status change
        if updated.assignee_id:
            current_user_name = current_user.full_name or current_user.username
            old_label = old_status.value.replace("_", " ").title() if old_status else "Unknown"
            new_label = update_data.status.value.replace("_", " ").title()
            _notify_task_assignee(
                db=db,
                task_id=task_id,
                assignee_employee_id=updated.assignee_id,
                type_="status_change",
                message=f"{current_user_name} changed the status of '{updated.title}' from {old_label} to {new_label}.",
                actor_id=current_user.id,
            )

    # Notify the new assignee if assignee changed
    if update_data.assignee_id is not None and update_data.assignee_id != old_assignee:
        current_user_name = current_user.full_name or current_user.username
        _notify_task_assignee(
            db=db,
            task_id=task_id,
            assignee_employee_id=update_data.assignee_id,
            type_="task_assigned",
            message=f"{current_user_name} assigned you to the task: '{updated.title}'.",
            actor_id=current_user.id,
        )

    return updated


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_by_id(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a task. Admin only."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete tasks",
        )

    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    log_activity(db, task_id, current_user.id, "deleted", "task", task.title, None)

    deleted = delete_task(db, task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )


# ══════════════════════════════════════════════
# Task Activity Endpoints
# ══════════════════════════════════════════════


@router.get("/{task_id}/activities")
async def list_task_activities(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the activity / audit trail for a task."""
    # Verify task exists
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Permission: non-admin users can only view activities on their own tasks
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view activity on tasks assigned to you",
            )

    activities = get_activities_for_task(db, task_id)
    return activities


# ══════════════════════════════════════════════
# Task Dependency Endpoints
# ══════════════════════════════════════════════


@router.get("/{task_id}/dependencies")
async def list_task_dependencies(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return dependencies for a task: both blocked_by and blocking."""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view dependencies on tasks assigned to you")

    blocked_by, blocking = get_dependencies_for_task(db, task_id)

    return {
        "blocked_by": [
            {
                "id": d.id,
                "task_id": str(d.task_id),
                "depends_on_task_id": str(d.depends_on_task_id),
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "title": d.depends_on_title,
                "status": d.depends_on_status,
                "priority": d.depends_on_priority,
            }
            for d in blocked_by
        ],
        "blocking": [
            {
                "id": d.id,
                "task_id": str(d.task_id),
                "depends_on_task_id": str(d.depends_on_task_id),
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "title": d.depends_on_title,
                "status": d.depends_on_status,
                "priority": d.depends_on_priority,
            }
            for d in blocking
        ],
    }


@router.post("/{task_id}/dependencies", status_code=status.HTTP_201_CREATED)
async def create_task_dependency(
    task_id: uuid.UUID,
    dep_data: TaskDependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a dependency: this task depends on another task."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can add dependencies")

    # Verify both tasks exist
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    depends_task = get_task(db, dep_data.depends_on_task_id)
    if not depends_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency task not found")

    # Prevent self-dependency
    if task_id == dep_data.depends_on_task_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A task cannot depend on itself")

    # Check for duplicate
    existing = db.query(TaskDependency).filter(
        TaskDependency.task_id == task_id,
        TaskDependency.depends_on_task_id == dep_data.depends_on_task_id,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This dependency already exists")

    dep = create_dependency(db, task_id, dep_data.depends_on_task_id)

    log_activity(db, task_id, current_user.id, "dependency_added", "dependency", None, f"Depends on: {depends_task.title}")

    return {
        "id": dep.id,
        "task_id": str(dep.task_id),
        "depends_on_task_id": str(dep.depends_on_task_id),
        "created_at": dep.created_at.isoformat() if dep.created_at else None,
        "title": depends_task.title,
        "status": depends_task.status.value if depends_task.status else None,
        "priority": depends_task.priority.value if depends_task.priority else None,
    }


@router.delete("/{task_id}/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_dependency(
    task_id: uuid.UUID,
    dependency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a dependency."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can remove dependencies")

    deleted = delete_dependency(db, dependency_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found")


# ══════════════════════════════════════════════
# SubTask / Checklist Endpoints
# ══════════════════════════════════════════════


@router.get("/{task_id}/subtasks")
async def list_subtasks(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all sub-tasks / checklist items for a task."""
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view sub-tasks on tasks assigned to you")

    from app.modules.tasks.crud import get_subtasks_for_task
    subtasks = get_subtasks_for_task(db, task_id)
    return [SubTaskResponse.from_orm_compat(st) for st in subtasks]


@router.post("/{task_id}/subtasks", status_code=status.HTTP_201_CREATED)
async def create_new_subtask(
    task_id: uuid.UUID,
    subtask_data: SubTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a sub-task / checklist item to a task."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can add sub-tasks")

    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    from app.modules.tasks.crud import create_subtask
    subtask = create_subtask(db, task_id, subtask_data)

    log_activity(db, task_id, current_user.id, "subtask_added", "subtask", None, subtask.title)

    return SubTaskResponse.from_orm_compat(subtask)


@router.patch("/{task_id}/subtasks/{subtask_id}")
async def update_subtask_by_id(
    task_id: uuid.UUID,
    subtask_id: int,
    update_data: SubTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a sub-task (title and/or toggle completed).

    Admins can update any field.
    Task assignees can only toggle the completed status.
    """
    # Verify task exists
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if not current_user.is_admin:
        # Non-admin: must be the task assignee and can only toggle completed
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update sub-tasks on tasks assigned to you",
            )

        update_fields = set(update_data.model_dump(exclude_unset=True).keys())
        if update_fields != {"completed"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees can only toggle the completed status of sub-tasks",
            )

    from app.modules.tasks.crud import update_subtask
    subtask = update_subtask(db, subtask_id, update_data)
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-task not found")

    # Log activity for completion toggle
    if update_data.completed is not None:
        action = "subtask_completed" if update_data.completed else "subtask_uncompleted"
        log_activity(db, task_id, current_user.id, action, "subtask", None, subtask.title)

    return SubTaskResponse.from_orm_compat(subtask)


@router.delete("/{task_id}/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask_by_id(
    task_id: uuid.UUID,
    subtask_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sub-task / checklist item."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can delete sub-tasks")

    from app.modules.tasks.crud import delete_subtask
    deleted = delete_subtask(db, subtask_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sub-task not found")


# ══════════════════════════════════════════════
# Task Comment Endpoints
# ══════════════════════════════════════════════


@router.get("/{task_id}/comments")
async def list_task_comments(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all comments for a task."""
    # Verify task exists
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Permission: non-admin users can only view comments on their own tasks
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view comments on tasks assigned to you",
            )

    from app.modules.tasks.crud import get_comments_for_task
    comments = get_comments_for_task(db, task_id)
    return comments


@router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_task_comment(
    task_id: uuid.UUID,
    comment_data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to a task."""
    # Verify task exists
    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    # Permission: non-admin users can only comment on their own tasks
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id is None or task.assignee_id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only comment on tasks assigned to you",
            )

    import json
    from app.modules.tasks.crud import create_comment
    comment = create_comment(db, task_id, comment_data, current_user.id)

    # Log activity
    log_activity(db, task_id, current_user.id, "commented", "comment", None, None)

    # Log mention activity for each mentioned user and create notifications
    if comment_data.mentioned_user_ids:
        try:
            from app.modules.auth.db_models import User as UserDB
            current_user_name = current_user.full_name or current_user.username
            mentioned = db.query(UserDB).filter(
                UserDB.id.in_(comment_data.mentioned_user_ids)
            ).all()
            for mentioned_user in mentioned:
                mention_name = mentioned_user.full_name or mentioned_user.username
                log_activity(
                    db, task_id, current_user.id,
                    "mentioned", "mention",
                    None, f"@{mention_name}",
                )
                # Create notification for mentioned user
                from app.modules.tasks.crud import create_notification
                create_notification(
                    db=db,
                    user_id=mentioned_user.id,
                    task_id=task_id,
                    type_="mention",
                    message=f"{current_user_name} mentioned you in a comment on '{task.title}'.",
                    actor_id=current_user.id,
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to log mention activities: %s", e)

    return comment


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(
    task_id: uuid.UUID,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment. Only the comment author can delete."""
    from app.modules.tasks.crud import delete_comment
    deleted = delete_comment(db, comment_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or you do not have permission to delete it",
        )


# ══════════════════════════════════════════════
# Analytics Endpoints
# ══════════════════════════════════════════════

import logging
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# AI-Powered Task Suggestion Endpoint
# ══════════════════════════════════════════════


@router.get("/ai/suggestions")
async def ai_task_suggestions(
    title: str = Query(..., min_length=1, max_length=500),
    description: Optional[str] = Query(None, max_length=2000),
    current_user: User = Depends(get_current_user),
):
    """Get AI-powered suggestions for a task draft.

    Given a title and optional description, returns:
      - Suggested subtasks (checklist items)
      - Suggested dependencies
      - Suggested assignee (role/department)
      - Suggested priority
      - Estimated effort in hours
      - An explanation of the reasoning
    """
    from app.modules.tasks.ai_service import get_task_suggestions

    suggestions = get_task_suggestions(title=title, description=description)
    return suggestions


@router.get("/{task_id}/ai/suggestions")
async def ai_task_suggestions_for_existing(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get AI-powered suggestions for an existing task (by ID)."""
    from app.modules.tasks.ai_service import get_task_suggestions

    task = get_task(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    suggestions = get_task_suggestions(
        title=task.title,
        description=task.description,
    )
    return suggestions


# ──────────────────────────────────────────────
# Analytics Endpoints
# ──────────────────────────────────────────────


def _analytics_base_query(db: Session, current_user: User) -> tuple[list | None, object]:
    """Build the base Task query with user filtering for analytics.

    Returns (None, query) for authorized users.
    Returns ([], query) for non-admin users without employee records (empty results).
    """
    query = db.query(Task)
    if not current_user.is_admin:
        employee_id = _get_employee_id(db, current_user)
        if employee_id:
            query = query.filter(Task.assignee_id == employee_id)
        else:
            # Non-admin with no employee record — return empty sentinel
            return [], query
    return None, query


@router.get("/analytics/summary")
async def analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a summary of task metrics: totals, completion rate, avg completion time, etc."""
    try:
        _, query = _analytics_base_query(db, current_user)
        if _ is not None:
            return _

        total = query.count()
        completed = query.filter(Task.status == Status.COMPLETED).count()
        overdue = query.filter(Task.status == Status.OVERDUE).count()
        in_progress = query.filter(Task.status == Status.ON_PROGRESS).count()
        on_hold = query.filter(Task.status == Status.ON_HOLD).count()
        on_review = query.filter(Task.status == Status.ON_REVIEW).count()
        pending = query.filter(Task.status == Status.TODO).count()

        completion_rate = round((completed / total * 100), 1) if total > 0 else 0.0

        # Average completion time (in hours)
        avg_time = db.query(
            func.avg(
                func.extract('epoch', Task.updated_at - Task.created_at) / 3600
            )
        ).filter(
            Task.status == Status.COMPLETED,
            Task.updated_at.isnot(None),
            Task.created_at.isnot(None),
        ).scalar()
        avg_completion_time = round(float(avg_time), 1) if avg_time else 0.0

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        created_today = query.filter(
            Task.created_at >= today_start,
            Task.created_at < today_end,
        ).count()

        completed_today = query.filter(
            Task.status == Status.COMPLETED,
            Task.updated_at >= today_start,
            Task.updated_at < today_end,
        ).count()

        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "pending_tasks": pending,
            "overdue_tasks": overdue,
            "in_progress_tasks": in_progress,
            "on_hold_tasks": on_hold,
            "on_review_tasks": on_review,
            "completion_rate": completion_rate,
            "avg_completion_time_hours": avg_completion_time,
            "tasks_created_today": created_today,
            "tasks_completed_today": completed_today,
        }
    except Exception as e:
        logger.exception("analytics_summary failed")
        raise HTTPException(status_code=500, detail=f"Analytics summary error: {str(e)}")


@router.get("/analytics/completion-trend")
async def analytics_completion_trend(
    period: str = Query("7d", pattern="^(7d|30d|90d)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return daily task completion and creation counts for the given period."""
    try:
        days = int(period.replace("d", ""))
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

        _, base_query = _analytics_base_query(db, current_user)
        if _ is not None:
            return {"labels": [], "created": [], "completed": [], "overdue": []}

        labels = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime("%Y-%m-%d"))

        created_counts = []
        completed_counts = []
        overdue_counts = []

        for day_label in labels:
            day_start = datetime.strptime(day_label, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            created = base_query.filter(
                Task.created_at >= day_start,
                Task.created_at < day_end,
            ).count()

            completed = base_query.filter(
                Task.status == Status.COMPLETED,
                Task.updated_at >= day_start,
                Task.updated_at < day_end,
            ).count()

            overdue = base_query.filter(
                Task.status == Status.OVERDUE,
                Task.updated_at >= day_start,
                Task.updated_at < day_end,
            ).count()

            created_counts.append(created)
            completed_counts.append(completed)
            overdue_counts.append(overdue)

        return {
            "labels": labels,
            "created": created_counts,
            "completed": completed_counts,
            "overdue": overdue_counts,
        }
    except Exception as e:
        logger.exception("analytics_completion_trend failed")
        raise HTTPException(status_code=500, detail=f"Analytics trend error: {str(e)}")


@router.get("/analytics/status-distribution")
async def analytics_status_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return task counts grouped by status."""
    try:
        query = db.query(Task.status, func.count(Task.id).label("count"))
        if not current_user.is_admin:
            employee_id = _get_employee_id(db, current_user)
            if employee_id:
                query = query.filter(Task.assignee_id == employee_id)
            else:
                return {s.value: 0 for s in Status}

        rows = query.group_by(Task.status).all()

        result = {s.value: 0 for s in Status}
        for status_val, count in rows:
            result[status_val.value] = count
        return result
    except Exception as e:
        logger.exception("analytics_status_distribution failed")
        raise HTTPException(status_code=500, detail=f"Analytics status error: {str(e)}")


@router.get("/analytics/priority-distribution")
async def analytics_priority_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return task counts grouped by priority."""
    try:
        query = db.query(Task.priority, func.count(Task.id).label("count"))
        if not current_user.is_admin:
            employee_id = _get_employee_id(db, current_user)
            if employee_id:
                query = query.filter(Task.assignee_id == employee_id)
            else:
                return {p.value: 0 for p in Priority}

        rows = query.group_by(Task.priority).all()

        result = {p.value: 0 for p in Priority}
        for priority_val, count in rows:
            result[priority_val.value] = count
        return result
    except Exception as e:
        logger.exception("analytics_priority_distribution failed")
        raise HTTPException(status_code=500, detail=f"Analytics priority error: {str(e)}")


@router.get("/analytics/team-workload")
async def analytics_team_workload(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-assignee task breakdown for the workload chart."""
    try:
        from app.modules.hr.db_models import Employee
        from app.modules.auth.db_models import User as UserDB

        if not current_user.is_admin:
            employee_id = _get_employee_id(db, current_user)
            if not employee_id:
                return []

            emp = db.query(Employee).options(
                joinedload(Employee.user), joinedload(Employee.department), joinedload(Employee.role)
            ).filter(Employee.id == employee_id).first()
            if not emp:
                return []

            name = emp.user.full_name if emp.user else "Unknown"
            tasks_data = db.query(
                Task.status, func.count(Task.id).label("count")
            ).filter(Task.assignee_id == employee_id).group_by(Task.status).all()

            workload = {"name": name, "total": 0, "todo": 0, "in_progress": 0, "on_hold": 0, "on_review": 0, "completed": 0, "overdue": 0}
            for status_val, count in tasks_data:
                workload["total"] += count
                key = status_val.value.lower()
                if key in workload:
                    workload[key] = count
            return [workload]

        employees = db.query(Employee).options(
            joinedload(Employee.user), joinedload(Employee.department), joinedload(Employee.role)
        ).all()

        result = []
        for emp in employees:
            name = emp.user.full_name if emp.user else f"Employee #{emp.id}"
            tasks_data = db.query(
                Task.status, func.count(Task.id).label("count")
            ).filter(Task.assignee_id == emp.id).group_by(Task.status).all()

            workload = {"name": name, "total": 0, "todo": 0, "in_progress": 0, "on_hold": 0, "on_review": 0, "completed": 0, "overdue": 0}
            for status_val, count in tasks_data:
                workload["total"] += count
                key = status_val.value.lower()
                if key in workload:
                    workload[key] = count
            result.append(workload)

        result.sort(key=lambda x: x["total"], reverse=True)
        return result
    except Exception as e:
        logger.exception("analytics_team_workload failed")
        raise HTTPException(status_code=500, detail=f"Analytics workload error: {str(e)}")


@router.get("/analytics/export")
async def analytics_export_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all tasks as a CSV file."""
    try:
        query = db.query(Task)
        if not current_user.is_admin:
            employee_id = _get_employee_id(db, current_user)
            if employee_id:
                query = query.filter(Task.assignee_id == employee_id)
            else:
                query = query.filter(Task.id.is_(None))

        tasks = query.order_by(Task.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Title", "Description", "Status", "Priority", "Assignee ID", "Due Date", "Created At", "Updated At", "Reason Note", "Proof Attachment"])

        for task in tasks:
            writer.writerow([
                str(task.id),
                task.title,
                task.description or "",
                task.status.value if task.status else "",
                task.priority.value if task.priority else "",
                task.assignee_id or "",
                task.due_date.isoformat() if task.due_date else "",
                task.created_at.isoformat() if task.created_at else "",
                task.updated_at.isoformat() if task.updated_at else "",
                task.reason_note or "",
                task.proof_attachment or "",
            ])

        output.seek(0)
        filename = f"tasks_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.exception("analytics_export_csv failed")
        raise HTTPException(status_code=500, detail=f"Analytics export error: {str(e)}")
