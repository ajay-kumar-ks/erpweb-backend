import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import JournalEntry, JournalLine


def create_bill_journal(db: Session, tenant_id: uuid.UUID, bill) -> JournalEntry:
    """
    Create a journal entry for a bill.
    Debit: Expense (account_id 5000)
    Credit: Accounts Payable (account_id 2000)
    """
    expense_account_id = 7
    ap_account_id = 4

    journal = JournalEntry(
        tenant_id=tenant_id,
        reference=bill.bill_number,
        description=f"Bill: {bill.description or bill.bill_number}",
        status="draft",
        date=bill.bill_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=expense_account_id,
        memo=f"Bill {bill.bill_number}",
        debit=Decimal(str(bill.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=ap_account_id,
        memo=f"Payable for Bill {bill.bill_number}",
        debit=Decimal("0"),
        credit=Decimal(str(bill.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)

    event_bus.publish(
        "bill.created",
        {
            "tenant_id": str(tenant_id),
            "bill_id": bill.id,
            "bill_number": bill.bill_number,
            "amount": float(bill.amount),
            "vendor_id": bill.vendor_id,
            "journal_id": journal.id,
        },
    )

    return journal


def create_vendor_payment_journal(db: Session, tenant_id: uuid.UUID, payment, bill) -> JournalEntry:
    """
    Create a journal entry for a vendor payment.
    Debit: Accounts Payable (account_id 2000)
    Credit: Cash (account_id 1000)
    """
    ap_account_id = 4
    cash_account_id = 1

    journal = JournalEntry(
        tenant_id=tenant_id,
        reference=payment.reference or f"VPY-{payment.id}",
        description=f"Payment for Bill {bill.bill_number}",
        status="draft",
        date=payment.payment_date,
    )
    db.add(journal)
    db.flush()

    debit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=ap_account_id,
        memo=f"Payment for Bill {bill.bill_number}",
        debit=Decimal(str(payment.amount)),
        credit=Decimal("0"),
    )
    db.add(debit_line)

    credit_line = JournalLine(
        tenant_id=tenant_id,
        journal_id=journal.id,
        account_id=cash_account_id,
        memo=f"Payment for Bill {bill.bill_number}",
        debit=Decimal("0"),
        credit=Decimal(str(payment.amount)),
    )
    db.add(credit_line)

    db.commit()
    db.refresh(journal)

    event_bus.publish(
        "bill.paid",
        {
            "tenant_id": str(tenant_id),
            "bill_id": bill.id,
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "journal_id": journal.id,
        },
    )

    return journal
