import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session
from app.core.event_bus import event_bus
from app.modules.accounts.models import ChartOfAccount, JournalEntry, JournalLine, LedgerEntry

DEFAULT_COA_ENTRIES = [
    {"account_code": "1000", "account_name": "Cash", "account_type": "Asset"},
    {"account_code": "1100", "account_name": "Bank", "account_type": "Asset"},
    {"account_code": "1200", "account_name": "Accounts Receivable", "account_type": "Asset"},
    {"account_code": "2000", "account_name": "Accounts Payable", "account_type": "Liability"},
    {"account_code": "3000", "account_name": "Capital", "account_type": "Equity"},
    {"account_code": "4000", "account_name": "Revenue", "account_type": "Revenue"},
    {"account_code": "5000", "account_name": "Expenses", "account_type": "Expense"},
]



def seed_default_chart_of_accounts(db: Session, tenant_id: uuid.UUID) -> None:
    existing_codes = {
        row[0]
        for row in db.query(ChartOfAccount.account_code)
        .filter(ChartOfAccount.tenant_id == tenant_id)
        .all()
    }

    entries = []
    for entry in DEFAULT_COA_ENTRIES:
        if entry["account_code"] in existing_codes:
            continue
        account = ChartOfAccount(
            tenant_id=tenant_id,
            account_code=entry["account_code"],
            account_name=entry["account_name"],
            account_type=entry["account_type"],
            is_active=True,
        )
        entries.append(account)

    if entries:
        db.add_all(entries)
        db.commit()



def validate_journal_lines(lines: List[JournalLine]) -> None:
    if not lines or len(lines) < 2:
        raise ValueError("Journal entry requires at least two lines.")

    total_debit = sum(Decimal(str(line.debit)) for line in lines)
    total_credit = sum(Decimal(str(line.credit)) for line in lines)

    if total_debit != total_credit:
        raise ValueError(
            f"Journal entry is unbalanced. Total debit {total_debit} must equal total credit {total_credit}."
        )

    if total_debit == Decimal("0") and total_credit == Decimal("0"):
        raise ValueError("Journal entry cannot contain only zero values.")



def post_journal_entry(db: Session, journal_entry: JournalEntry) -> JournalEntry:
    if journal_entry.status != "approved":
        raise ValueError("Only approved journal entries can be posted.")

    existing_ledger_entry = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.journal_id == journal_entry.id)
        .first()
    )
    if existing_ledger_entry:
        raise ValueError("This journal entry has already been posted to the ledger.")

    # Query lines explicitly since relationship was removed
    lines = db.query(JournalLine).filter(
        JournalLine.journal_id == journal_entry.id,
        JournalLine.tenant_id == journal_entry.tenant_id
    ).all()

    for line in lines:
        ledger_entry = LedgerEntry(
            tenant_id=journal_entry.tenant_id,
            journal_id=journal_entry.id,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            posting_date=journal_entry.date,
        )
        db.add(ledger_entry)

    journal_entry.status = "posted"
    journal_entry.posted_at = datetime.utcnow()
    db.commit()
    db.refresh(journal_entry)

    event_bus.publish(
        "journal.posted",
        {
            "tenant_id": str(journal_entry.tenant_id),
            "journal_id": journal_entry.id,
            "reference": journal_entry.reference,
            "description": journal_entry.description,
            "posting_date": journal_entry.posted_at.isoformat(),
            "lines": [
                {
                    "account_id": line.account_id,
                    "debit": float(line.debit),
                    "credit": float(line.credit),
                }
                for line in lines
            ],
        },
    )

    return journal_entry
