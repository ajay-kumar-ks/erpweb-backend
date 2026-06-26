from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.event_bus import event_bus
from app.core.database import SessionLocal
from app.modules.accounts.models import ChartOfAccount, JournalEntry, JournalLine
from app.modules.accounts.services import post_journal_entry


_SALARY_EXPENSE_CODE = "5000"
_SALARY_PAYABLE_CODE = "2100"


def _get_account_id_by_code(db: Session, account_code: str) -> int:
    row = db.query(ChartOfAccount.id).filter(ChartOfAccount.account_code == account_code).first()
    if not row:
        raise ValueError(f"COA account not found for code={account_code}")
    return row[0]


def _resolve_cash_account(db: Session) -> int:
    """Try Cash (1000) first, then fall back to Bank (1100)."""
    for code in ("1000", "1100"):
        try:
            return _get_account_id_by_code(db, code)
        except ValueError:
            continue
    raise ValueError("Neither Cash (1000) nor Bank (1100) account found in COA.")


def handle_salary_processed(payload: dict) -> None:
    """Step 1 — Accrue salary expense: Dr Salary Expense, Cr Salary Payable.

    Expected payload fields:
      - amount (number, required)
      - reference (optional)
      - timestamp (optional)
    """
    db: Session = SessionLocal()
    try:
        amount_raw = payload.get("amount")
        if amount_raw is None:
            return

        amount = Decimal(str(amount_raw))
        if amount <= 0:
            return

        expense_account_id = _get_account_id_by_code(db, _SALARY_EXPENSE_CODE)
        payable_account_id = _get_account_id_by_code(db, _SALARY_PAYABLE_CODE)

        when = payload.get("timestamp")
        journal_date = datetime.fromisoformat(when) if when else datetime.utcnow()

        journal_ref = payload.get("reference") or f"ACCRUAL-SAL-{int(journal_date.timestamp())}"

        journal = JournalEntry(
            reference=journal_ref,
            description="Payroll salary accrual",
            status="approved",
            date=journal_date,
        )
        db.add(journal)
        db.flush()

        expense_line = JournalLine(
            journal_id=journal.id,
            account_id=expense_account_id,
            memo="Payroll salary expense (accrual)",
            debit=amount,
            credit=Decimal("0"),
        )
        payable_line = JournalLine(
            journal_id=journal.id,
            account_id=payable_account_id,
            memo="Salary payable (accrual)",
            debit=Decimal("0"),
            credit=amount,
        )
        db.add(expense_line)
        db.add(payable_line)
        db.flush()

        post_journal_entry(db, journal)
        db.commit()

        # Publish salary.accrued so downstream (e.g., payment trigger) can act
        event_bus.publish(
            "salary.accrued",
            {
                "salary_event_reference": journal_ref,
                "accrual_journal_id": journal.id,
                "amount": float(amount),
                "payable_account_id": payable_account_id,
            },
        )
    except Exception as exc:
        db.rollback()
        print(f"[salary_event_handler] Error accruing salary: {exc}")
    finally:
        db.close()


def handle_salary_paid(payload: dict) -> None:
    """Step 2 — Pay the accrued salary: Dr Salary Payable, Cr Cash/Bank.

    Expected payload fields:
      - amount (number, required)
      - reference (optional)
      - timestamp (optional)
    """
    db: Session = SessionLocal()
    try:
        amount_raw = payload.get("amount")
        if amount_raw is None:
            return

        amount = Decimal(str(amount_raw))
        if amount <= 0:
            return

        payable_account_id = _get_account_id_by_code(db, _SALARY_PAYABLE_CODE)
        cash_account_id = _resolve_cash_account(db)

        when = payload.get("timestamp")
        journal_date = datetime.fromisoformat(when) if when else datetime.utcnow()

        journal_ref = payload.get("reference") or f"PAY-SAL-{int(journal_date.timestamp())}"

        journal = JournalEntry(
            reference=journal_ref,
            description="Payroll salary payment",
            status="approved",
            date=journal_date,
        )
        db.add(journal)
        db.flush()

        payable_reversal_line = JournalLine(
            journal_id=journal.id,
            account_id=payable_account_id,
            memo="Salary payable settlement",
            debit=amount,
            credit=Decimal("0"),
        )
        cash_line = JournalLine(
            journal_id=journal.id,
            account_id=cash_account_id,
            memo="Cash payment for payroll",
            debit=Decimal("0"),
            credit=amount,
        )
        db.add(payable_reversal_line)
        db.add(cash_line)
        db.flush()

        post_journal_entry(db, journal)
        db.commit()

        event_bus.publish(
            "salary.paid",
            {
                "salary_event_reference": journal_ref,
                "payment_journal_id": journal.id,
                "amount": float(amount),
            },
        )
    except Exception as exc:
        db.rollback()
        print(f"[salary_event_handler] Error paying salary: {exc}")
    finally:
        db.close()


def register_salary_event_handlers() -> None:
    event_bus.subscribe("salary.processed", handle_salary_processed)
    event_bus.subscribe("salary.paid", handle_salary_paid)
