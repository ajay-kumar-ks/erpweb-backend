from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import JournalEntry, JournalLine
from app.modules.accounts.transaction_models import Expense, Income


def create_expense_journal(db: Session, expense: Expense) -> JournalEntry:
    """
    Create a journal entry for an expense.
    Debit: Expense Account
    Credit: Cash/Bank (account_id 1100)
    """
    cash_account_id = 2

    journal = JournalEntry(
        tenant_id=expense.tenant_id,
        reference=expense.reference or f"EXP-{expense.id}",
        description=f"Expense: {expense.description}",
        status="draft",
        date=expense.expense_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=expense.tenant_id,
        journal_id=journal.id,
        account_id=expense.account_id,
        memo=expense.description,
        debit=Decimal(str(expense.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=expense.tenant_id,
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Payment for {expense.description}",
        debit=Decimal("0"),
        credit=Decimal(str(expense.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)
    return journal


def create_income_journal(db: Session, income: Income) -> JournalEntry:
    """
    Create a journal entry for income.
    Debit: Cash/Bank (account_id 1100)
    Credit: Income Account
    """
    cash_account_id = 2

    journal = JournalEntry(
        tenant_id=income.tenant_id,
        reference=income.reference or f"INC-{income.id}",
        description=f"Income: {income.description}",
        status="draft",
        date=income.income_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=income.tenant_id,
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Receipt from {income.description}",
        debit=Decimal(str(income.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=income.tenant_id,
        journal_id=journal.id,
        account_id=income.account_id,
        memo=income.description,
        debit=Decimal("0"),
        credit=Decimal(str(income.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)
    return journal
