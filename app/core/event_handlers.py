from app.core.database import SessionLocal
from app.core.event_bus import event_bus
from app.core.event_store import EventStore


def _make_event_recorder(event_type: str):
    def record(payload: dict):
        db = SessionLocal()
        try:
            event_record = EventStore(
                event_type=event_type,
                payload=payload,
                processed=False,
            )
            db.add(event_record)
            db.commit()
        finally:
            db.close()

    return record


def register_event_handlers() -> None:
    event_names = [
        "invoice.created",
        "invoice.paid",
        "bill.created",
        "bill.paid",
        "expense.created",
        "income.created",
        "salary.processed",
        "salary.paid",
        "budget.created",
        "budget.exceeded",
        "journal.posted",
    ]

    for event_name in event_names:
        event_bus.subscribe(event_name, _make_event_recorder(event_name))
