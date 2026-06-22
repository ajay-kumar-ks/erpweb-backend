from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.modules.accounts.models import LedgerEntry
from app.core.event_bus import event_bus


def calculate_budget_consumption(db: Session, budget_line) -> None:
    """Calculate spent amount and consumption percentage for a budget line."""
    ledger_entries = (
        db.query(func.sum(LedgerEntry.debit).label("total_spent"))
        .filter(
            LedgerEntry.account_id == budget_line.account_id,
            LedgerEntry.tenant_id == budget_line.tenant_id,
        )
        .first()
    )

    spent = ledger_entries.total_spent or Decimal("0")
    budget_line.spent_amount = spent

    if budget_line.allocated_amount > 0:
        percentage = (spent / budget_line.allocated_amount) * 100
        budget_line.consumed_percentage = Decimal(str(min(percentage, 100)))

        if percentage > 100:
            event_bus.publish(
                "budget.exceeded",
                {
                    "budget_line_id": budget_line.id,
                    "account_id": budget_line.account_id,
                    "allocated": float(budget_line.allocated_amount),
                    "spent": float(spent),
                    "percentage": float(percentage),
                },
            )

    db.commit()
