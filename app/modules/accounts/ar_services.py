from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import JournalEntry, JournalLine
from app.core.database import commit_or_rollback


def create_invoice_journal(db: Session, invoice) -> JournalEntry:
    """Create a journal entry for an invoice.
    Debit: Accounts Receivable (account_id 1200)
    Credit: Revenue (account_id 4000)
    """
    ar_account_id = 3
    revenue_account_id = 6

    journal = JournalEntry(
        reference=invoice.invoice_number,
        description=f"Invoice: {invoice.description or invoice.invoice_number}",
        status="draft",
        date=invoice.invoice_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        journal_id=journal.id,
        account_id=ar_account_id,
        memo=f"Invoice {invoice.invoice_number}",
        debit=Decimal(str(invoice.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        journal_id=journal.id,
        account_id=revenue_account_id,
        memo=f"Revenue from invoice {invoice.invoice_number}",
        debit=Decimal("0"),
        credit=Decimal(str(invoice.amount)),
    )
    db.add(credit_line)

    commit_or_rollback(db)
    db.refresh(journal)

    event_bus.publish(
        "invoice.created",
        {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": float(invoice.amount),
            "customer_id": invoice.customer_id,
            "journal_id": journal.id,
        },
    )

    return journal


def create_payment_journal(db: Session, payment, invoice) -> JournalEntry:
    """Create a journal entry for a customer payment.
    Debit: Cash (account_id 1000)
    Credit: Accounts Receivable (account_id 1200)
    """
    cash_account_id = 1
    ar_account_id = 3

    journal = JournalEntry(
        reference=payment.reference or f"PMT-{payment.id}",
        description=f"Payment for Invoice {invoice.invoice_number}",
        status="draft",
        date=payment.payment_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Payment for Invoice {invoice.invoice_number}",
        debit=Decimal(str(payment.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        journal_id=journal.id,
        account_id=ar_account_id,
        memo=f"Payment received for {invoice.invoice_number}",
        debit=Decimal("0"),
        credit=Decimal(str(payment.amount)),
    )
    db.add(credit_line)

    commit_or_rollback(db)
    db.refresh(journal)

    event_bus.publish(
        "invoice.paid",
        {
            "invoice_id": invoice.id,
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "journal_id": journal.id,
        },
    )

    return journal