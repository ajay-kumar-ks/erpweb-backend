import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import JournalEntry, JournalLine


def create_invoice_journal(db: Session, tenant_id: uuid.UUID, invoice) -> JournalEntry:
    """
    Create a journal entry for an invoice.
    Debit: Accounts Receivable (account_id 1200)
    Credit: Revenue (account_id 4000)
    """
    ar_account_id = 3
    revenue_account_id = 6

    journal = JournalEntry(
        tenant_id=tenant_id,
        reference=invoice.invoice_number,
        description=f"Invoice: {invoice.description or invoice.invoice_number}",
        status="draft",
        date=invoice.invoice_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=ar_account_id,
        memo=f"Invoice {invoice.invoice_number}",
        debit=Decimal(str(invoice.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=revenue_account_id,
        memo=f"Revenue from invoice {invoice.invoice_number}",
        debit=Decimal("0"),
        credit=Decimal(str(invoice.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)

    event_bus.publish(
        "invoice.created",
        {
            "tenant_id": str(tenant_id),
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": float(invoice.amount),
            "customer_id": invoice.customer_id,
            "journal_id": journal.id,
        },
    )

    return journal


def create_payment_journal(db: Session, tenant_id: uuid.UUID, payment, invoice) -> JournalEntry:
    """
    Create a journal entry for a customer payment.
    Debit: Cash (account_id 1000)
    Credit: Accounts Receivable (account_id 1200)
    """
    cash_account_id = 1
    ar_account_id = 3

    journal = JournalEntry(
        tenant_id=tenant_id,
        reference=payment.reference or f"PMT-{payment.id}",
        description=f"Payment for Invoice {invoice.invoice_number}",
        status="draft",
        date=payment.payment_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Payment for Invoice {invoice.invoice_number}",
        debit=Decimal(str(payment.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=ar_account_id,
        memo=f"Payment received for {invoice.invoice_number}",
        debit=Decimal("0"),
        credit=Decimal(str(payment.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)

    event_bus.publish(
        "invoice.paid",
        {
            "tenant_id": str(tenant_id),
            "invoice_id": invoice.id,
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "journal_id": journal.id,
        },
    )

    return journal
