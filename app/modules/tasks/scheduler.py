import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.event_bus import event_bus
from app.modules.tasks.db_models import Task, Status

logger = logging.getLogger(__name__)
OVERDUE_CHECK_INTERVAL = 60  # seconds


def check_and_flag_overdue_tasks() -> int:
    """
    Query tasks where due_date < now and status is not COMPLETED or OVERDUE,
    flag them as OVERDUE, and return the count of tasks flagged.
    """
    session: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        overdue_tasks = (
            session.query(Task)
            .filter(
                Task.due_date < now,
                Task.status.notin_([Status.COMPLETED, Status.OVERDUE]),
            )
            .all()
        )

        if not overdue_tasks:
            return 0

        # Collect event payloads before mutating
        event_payloads = []
        for task in overdue_tasks:
            task.status = Status.OVERDUE
            event_payloads.append({
                "task_id": str(task.id),
                "assignee_id": task.assignee_id,
                "due_date": task.due_date.isoformat(),
            })

        session.commit()

        # Publish events only after successful commit
        for payload in event_payloads:
            event_bus.publish("task.overdue", payload)

        return len(overdue_tasks)
    except Exception as e:
        logger.error("Overdue scheduler error: %s", e)
        session.rollback()
        return 0
    finally:
        session.close()


async def run_overdue_scheduler() -> None:
    """Background loop that periodically flags overdue tasks."""
    logger.info("Overdue scheduler started (checking every %ds)", OVERDUE_CHECK_INTERVAL)
    while True:
        try:
            flagged = await asyncio.to_thread(check_and_flag_overdue_tasks)
            if flagged:
                logger.info("Flagged %d overdue task(s)", flagged)
        except Exception as e:
            logger.error("Overdue scheduler loop error: %s", e)
        await asyncio.sleep(OVERDUE_CHECK_INTERVAL)
