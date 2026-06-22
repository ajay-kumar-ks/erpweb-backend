import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.modules.tasks.db_models import Task, Priority, Status
from app.modules.tasks.schemas import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


def _enrich_tasks_with_employees(db: Session, tasks: list[Task]) -> list[Task]:
    """Batch-load employee details for a list of tasks to avoid N+1 queries.

    Collects all unique assignee_ids, queries the HR employees table once,
    and attaches the details to each task.
    """
    if not tasks:
        return tasks

    # Collect unique assignee IDs
    assignee_ids = list({t.assignee_id for t in tasks if t.assignee_id is not None})
    if assignee_ids:
        try:
            from app.modules.hr.db_models import Employee
            from app.modules.auth.db_models import User as UserDB
            from sqlalchemy.orm import joinedload

            employees = (
                db.query(Employee)
                .options(joinedload(Employee.user), joinedload(Employee.department), joinedload(Employee.role))
                .filter(Employee.id.in_(assignee_ids))
                .all()
            )

            # Build lookup: employee_id -> (name, email, department, designation)
            lookup = {}
            for emp in employees:
                lookup[emp.id] = (
                    emp.user.full_name if emp.user else None,
                    emp.user.email if emp.user else None,
                    emp.department.name if emp.department else None,
                    emp.role.name if emp.role else None,
                )

            # Attach to each task
            for task in tasks:
                if task.assignee_id in lookup:
                    task.assignee_name, task.assignee_email, task.assignee_department, task.assignee_designation = lookup[task.assignee_id]
                else:
                    task.assignee_name = task.assignee_email = task.assignee_department = task.assignee_designation = None
        except Exception as e:
            logger.warning("Failed to enrich tasks with employee data: %s", e)

    # Batch-load subtask counts for each task
    try:
        from app.modules.tasks.db_models import SubTask
        from sqlalchemy import func

        task_ids = [t.id for t in tasks]
        subtask_stats = (
            db.query(
                SubTask.task_id,
                func.count(SubTask.id).label("total"),
                func.sum(SubTask.completed).label("completed"),
            )
            .filter(SubTask.task_id.in_(task_ids))
            .group_by(SubTask.task_id)
            .all()
        )

        stats_lookup = {}
        for task_id, total, completed in subtask_stats:
            stats_lookup[task_id] = (total, completed or 0)

        for task in tasks:
            stats = stats_lookup.get(task.id, (0, 0))
            task.subtask_count = stats[0]
            task.subtask_completed_count = stats[1]
    except Exception as e:
        logger.warning("Failed to enrich tasks with subtask counts: %s", e)
        for task in tasks:
            task.subtask_count = 0
            task.subtask_completed_count = 0

    return tasks


def create_task(db: Session, task_data: TaskCreate, created_by: int) -> Task:
    """Create a new task and return it."""
    task = Task(
        title=task_data.title,
        description=task_data.description,
        assignee_id=task_data.assignee_id,
        created_by=created_by,
        priority=task_data.priority,
        status=task_data.status,
        reason_note=task_data.reason_note,
        proof_attachment=task_data.proof_attachment,
        due_date=task_data.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    results = _enrich_tasks_with_employees(db, [task])
    return results[0] if results else task


def get_tasks(
    db: Session,
    status: Optional[Status] = None,
    priority: Optional[Priority] = None,
    assignee_id: Optional[int] = None,
    search: Optional[str] = None,
    employee_id: Optional[int] = None,
) -> list[Task]:
    """List tasks with optional filters.

    If employee_id is provided, only tasks assigned to that employee are returned.
    """
    query = db.query(Task)

    if status is not None:
        query = query.filter(Task.status == status)
    if priority is not None:
        query = query.filter(Task.priority == priority)
    if assignee_id is not None:
        query = query.filter(Task.assignee_id == assignee_id)
    if employee_id is not None:
        query = query.filter(Task.assignee_id == employee_id)
    if search:
        query = query.filter(Task.title.ilike(f"%{search}%"))

    tasks = query.order_by(Task.due_date.asc()).all()
    return _enrich_tasks_with_employees(db, tasks)


def get_task(db: Session, task_id: uuid.UUID) -> Optional[Task]:
    """Fetch a single task by ID."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        results = _enrich_tasks_with_employees(db, [task])
        return results[0] if results else task
    return task


def update_task(db: Session, task_id: uuid.UUID, update_data: TaskUpdate) -> Optional[Task]:
    """Update a task with partial data and return it. Returns None if not found."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    results = _enrich_tasks_with_employees(db, [task])
    return results[0] if results else task


def delete_task(db: Session, task_id: uuid.UUID) -> bool:
    """Delete a task by ID. Returns True if deleted, False if not found."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True


# ══════════════════════════════════════════════
# Task Comment CRUD
# ══════════════════════════════════════════════

from app.modules.tasks.db_models import TaskComment
from app.modules.tasks.schemas import TaskCommentCreate


def _enrich_comments_with_users(db: Session, comments: list[TaskComment]) -> list[TaskComment]:
    """Batch-load user details for a list of comments to avoid N+1 queries."""
    user_ids = list({c.user_id for c in comments if c.user_id is not None})
    if not user_ids:
        return comments

    try:
        from app.modules.auth.db_models import User as UserDB

        users = db.query(UserDB).filter(UserDB.id.in_(user_ids)).all()
        lookup = {u.id: (u.full_name or u.username, u.email) for u in users}

        for comment in comments:
            if comment.user_id in lookup:
                comment.user_name, comment.user_email = lookup[comment.user_id]
            else:
                comment.user_name = comment.user_email = None
    except Exception as e:
        logger.warning("Failed to enrich comments with user data: %s", e)

    return comments


def get_comments_for_task(db: Session, task_id: uuid.UUID) -> list[TaskComment]:
    """Return all comments for a task, ordered by creation time ascending."""
    comments = db.query(TaskComment).filter(
        TaskComment.task_id == task_id
    ).order_by(TaskComment.created_at.asc()).all()
    return _enrich_comments_with_users(db, comments)


def create_comment(
    db: Session,
    task_id: uuid.UUID,
    comment_data: TaskCommentCreate,
    user_id: int,
) -> TaskComment:
    """Create a new comment on a task, optionally storing mentioned user IDs."""
    import json

    mentioned_ids = comment_data.mentioned_user_ids
    mentioned_json = json.dumps(mentioned_ids) if mentioned_ids else None

    comment = TaskComment(
        task_id=task_id,
        user_id=user_id,
        content=comment_data.content,
        mentioned_user_ids=mentioned_json,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    result = _enrich_comments_with_users(db, [comment])
    return result[0] if result else comment


def delete_comment(db: Session, comment_id: int, user_id: int) -> bool:
    """Delete a comment by ID. Only the comment author can delete.
    Returns True if deleted, False if not found or not author."""
    comment = db.query(TaskComment).filter(TaskComment.id == comment_id).first()
    if not comment:
        return False
    if comment.user_id != user_id:
        return False
    db.delete(comment)
    db.commit()
    return True


# ══════════════════════════════════════════════
# Task Activity / Audit Trail CRUD
# ══════════════════════════════════════════════

from app.modules.tasks.db_models import TaskActivity


def log_activity(
    db: Session,
    task_id: uuid.UUID,
    user_id: int,
    action: str,
    field_name: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> TaskActivity:
    """Create an activity log entry for a task."""
    activity = TaskActivity(
        task_id=task_id,
        user_id=user_id,
        action=action,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def _enrich_activities_with_users(db: Session, activities: list[TaskActivity]) -> list[TaskActivity]:
    """Batch-load user details for a list of activities."""
    user_ids = list({a.user_id for a in activities if a.user_id is not None})
    if not user_ids:
        return activities

    try:
        from app.modules.auth.db_models import User as UserDB
        users = db.query(UserDB).filter(UserDB.id.in_(user_ids)).all()
        lookup = {u.id: (u.full_name or u.username, u.email) for u in users}

        for activity in activities:
            if activity.user_id in lookup:
                activity.user_name, activity.user_email = lookup[activity.user_id]
            else:
                activity.user_name = activity.user_email = None
    except Exception as e:
        logger.warning("Failed to enrich activities with user data: %s", e)

    return activities


def get_activities_for_task(db: Session, task_id: uuid.UUID) -> list[TaskActivity]:
    """Return all activity log entries for a task, most recent first."""
    activities = db.query(TaskActivity).filter(
        TaskActivity.task_id == task_id
    ).order_by(TaskActivity.created_at.desc()).all()
    return _enrich_activities_with_users(db, activities)


# ══════════════════════════════════════════════
# Task Dependency CRUD
# ══════════════════════════════════════════════

from app.modules.tasks.db_models import TaskDependency


def create_dependency(db: Session, task_id: uuid.UUID, depends_on_task_id: uuid.UUID) -> TaskDependency:
    """Create a dependency relationship.
    task_id depends on depends_on_task_id (i.e. task_id is blocked by depends_on_task_id).
    """
    dep = TaskDependency(
        task_id=task_id,
        depends_on_task_id=depends_on_task_id,
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep


def _enrich_dependencies_with_tasks(db: Session, dependencies: list[TaskDependency]) -> list[TaskDependency]:
    """Batch-load task details for dependency targets."""
    task_ids = list({d.depends_on_task_id for d in dependencies if d.depends_on_task_id is not None})
    if not task_ids:
        return dependencies

    try:
        tasks = db.query(Task).filter(Task.id.in_(task_ids)).all()
        lookup = {t.id: (t.title, t.status.value if t.status else None, t.priority.value if t.priority else None) for t in tasks}

        for dep in dependencies:
            if dep.depends_on_task_id in lookup:
                dep.depends_on_title, dep.depends_on_status, dep.depends_on_priority = lookup[dep.depends_on_task_id]
            else:
                dep.depends_on_title = "(deleted task)"
                dep.depends_on_status = None
                dep.depends_on_priority = None
    except Exception as e:
        logger.warning("Failed to enrich dependencies with task data: %s", e)

    return dependencies


def get_dependencies_for_task(db: Session, task_id: uuid.UUID) -> tuple[list[TaskDependency], list[TaskDependency]]:
    """Return (blocked_by, blocking) dependencies for a task.

    - blocked_by: tasks that this task depends on (this task is blocked by them)
    - blocking: tasks that depend on this task (they are blocked by this task)
    """
    blocked_by = db.query(TaskDependency).filter(
        TaskDependency.task_id == task_id
    ).all()
    blocked_by = _enrich_dependencies_with_tasks(db, blocked_by)

    blocking = db.query(TaskDependency).filter(
        TaskDependency.depends_on_task_id == task_id
    ).all()
    blocking = _enrich_dependencies_with_tasks(db, blocking)

    return blocked_by, blocking


def delete_dependency(db: Session, dependency_id: int) -> bool:
    """Delete a dependency by ID. Returns True if deleted."""
    dep = db.query(TaskDependency).filter(TaskDependency.id == dependency_id).first()
    if not dep:
        return False
    db.delete(dep)
    db.commit()
    return True


# ══════════════════════════════════════════════
# SubTask / Checklist CRUD
# ══════════════════════════════════════════════

from app.modules.tasks.db_models import SubTask
from app.modules.tasks.schemas import SubTaskCreate, SubTaskUpdate


def create_subtask(db: Session, task_id: uuid.UUID, subtask_data: SubTaskCreate) -> SubTask:
    """Create a new sub-task for a given task."""
    subtask = SubTask(
        task_id=task_id,
        title=subtask_data.title,
    )
    db.add(subtask)
    db.commit()
    db.refresh(subtask)
    return subtask


def get_subtasks_for_task(db: Session, task_id: uuid.UUID) -> list[SubTask]:
    """Return all sub-tasks for a task, ordered by creation time ascending."""
    return db.query(SubTask).filter(
        SubTask.task_id == task_id
    ).order_by(SubTask.created_at.asc()).all()


def update_subtask(db: Session, subtask_id: int, update_data: SubTaskUpdate) -> Optional[SubTask]:
    """Update a sub-task's title and/or completed status. Returns None if not found."""
    subtask = db.query(SubTask).filter(SubTask.id == subtask_id).first()
    if not subtask:
        return None

    update_dict = update_data.model_dump(exclude_unset=True)
    # Convert boolean completed to int for DB storage
    if "completed" in update_dict:
        update_dict["completed"] = 1 if update_dict["completed"] else 0

    for field, value in update_dict.items():
        setattr(subtask, field, value)

    db.commit()
    db.refresh(subtask)
    return subtask


def delete_subtask(db: Session, subtask_id: int) -> bool:
    """Delete a sub-task by ID. Returns True if deleted."""
    subtask = db.query(SubTask).filter(SubTask.id == subtask_id).first()
    if not subtask:
        return False
    db.delete(subtask)
    db.commit()
    return True


# ══════════════════════════════════════════════
# Task Notification CRUD
# ══════════════════════════════════════════════

from app.modules.tasks.db_models import TaskNotification
from datetime import datetime, timezone


def create_notification(
    db: Session,
    user_id: int,
    task_id: uuid.UUID,
    type_: str,
    message: str,
    actor_id: int,
) -> TaskNotification:
    """Create a notification for a user about a task event."""
    notification = TaskNotification(
        user_id=user_id,
        task_id=task_id,
        type=type_,
        message=message,
        actor_id=actor_id,
        read=0,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_notifications_for_user(
    db: Session,
    user_id: int,
    limit: int = 50,
    unread_only: bool = False,
) -> list[TaskNotification]:
    """Return the most recent notifications for a user, enriched with actor name and task title."""
    query = db.query(TaskNotification).filter(
        TaskNotification.user_id == user_id
    )
    if unread_only:
        query = query.filter(TaskNotification.read == 0)

    notifications = query.order_by(TaskNotification.created_at.desc()).limit(limit).all()

    # Enrich with actor name and task title
    try:
        from app.modules.auth.db_models import User as UserDB
        user_ids = list({n.actor_id for n in notifications})
        users = db.query(UserDB).filter(UserDB.id.in_(user_ids)).all() if user_ids else []
        user_lookup = {u.id: u.full_name or u.username for u in users}

        task_ids = list({n.task_id for n in notifications})
        tasks = db.query(Task).filter(Task.id.in_(task_ids)).all() if task_ids else []
        task_lookup = {t.id: t.title for t in tasks}

        for n in notifications:
            n.actor_name = user_lookup.get(n.actor_id)
            n.task_title = task_lookup.get(n.task_id)
    except Exception as e:
        logger.warning("Failed to enrich notifications: %s", e)
        for n in notifications:
            n.actor_name = None
            n.task_title = None

    return notifications


def get_unread_notification_count(db: Session, user_id: int) -> int:
    """Return the number of unread notifications for a user."""
    return db.query(TaskNotification).filter(
        TaskNotification.user_id == user_id,
        TaskNotification.read == 0,
    ).count()


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a single notification as read. Returns True if updated."""
    notification = db.query(TaskNotification).filter(
        TaskNotification.id == notification_id,
        TaskNotification.user_id == user_id,
    ).first()
    if not notification:
        return False
    notification.read = 1
    db.commit()
    return True


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    """Mark all unread notifications as read for a user. Returns count of updated rows."""
    result = db.query(TaskNotification).filter(
        TaskNotification.user_id == user_id,
        TaskNotification.read == 0,
    ).update({"read": 1})
    db.commit()
    return result
