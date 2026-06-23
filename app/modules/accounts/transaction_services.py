from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import ChartOfAccount, JournalEntry, JournalLine
from app.modules.accounts.transaction_models import Expense, Income
from app.core.database import commit_or_rollback


def _get_cash_account_id(db: Session) -> int:
    account = db.query(ChartOfAccount.id).filter(ChartOfAccount.account_code == "1000").first()
    if account:
        return account[0]

    account = db.query(ChartOfAccount.id).filter(ChartOfAccount.account_code == "1100").first()
    if account:
        return account[0]

    account = db.query(ChartOfAccount.id).filter(ChartOfAccount.account_type.ilike("asset")).first()
    if account:
        return account[0]

    raise ValueError("No cash or asset account found in the chart of accounts.")


def create_expense_journal(db: Session, expense: Expense) -> JournalEntry:
    """
    Create a journal entry for an expense.
    Debit: Expense Account
    Credit: Cash/Bank
    """
    cash_account_id = _get_cash_account_id(db)

    journal = JournalEntry(
        reference=expense.reference or f"EXP-{expense.id}",
        description=f"Expense: {expense.description}",
        status="draft",
        date=expense.expense_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        journal_id=journal.id,
        account_id=expense.account_id,
        memo=expense.description,
        debit=Decimal(str(expense.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Payment for {expense.description}",
        debit=Decimal("0"),
        credit=Decimal(str(expense.amount)),
    )
    db.add(credit_line)

    commit_or_rollback(db)
    db.refresh(journal)
    return journal


def create_income_journal(db: Session, income: Income) -> JournalEntry:
    """
    Create a journal entry for income.
    Debit: Cash/Bank
    Credit: Income Account
    """
    cash_account_id = _get_cash_account_id(db)

    journal = JournalEntry(
        reference=income.reference or f"INC-{income.id}",
        description=f"Income: {income.description}",
        status="draft",
        date=income.income_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Receipt from {income.description}",
        debit=Decimal(str(income.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        journal_id=journal.id,
        account_id=income.account_id,
        memo=income.description,
        debit=Decimal("0"),
        credit=Decimal(str(income.amount)),
    )
    db.add(credit_line)

    commit_or_rollback(db)
    db.refresh(journal)
    return journal