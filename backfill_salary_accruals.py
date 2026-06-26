"""
One-time migration: Create salary accrual journal entries for existing
employees who have a salary but no matching accrual entry in Accounts.

This reuses the same accounting logic as salary_event_handlers.py:
  Dr Salary Expense (5000)   →  Cr Salary Payable (2100)

Run:  python backfill_salary_accruals.py
"""

import sys
import os
# Force UTF-8 output to avoid UnicodeEncodeError on Windows
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
os.environ["PYTHONIOENCODING"] = "utf-8"

from datetime import datetime
from decimal import Decimal

from sqlalchemy import text

from app.core.database import SessionLocal
from app.modules.accounts.models import ChartOfAccount, JournalEntry, JournalLine, LedgerEntry
from app.modules.accounts.services import post_journal_entry


SALARY_EXPENSE_CODE = "5000"
SALARY_PAYABLE_CODE = "2100"


def _get_account_id_by_code(db, account_code: str) -> int:
    row = db.query(ChartOfAccount.id).filter(
        ChartOfAccount.account_code == account_code
    ).first()
    if not row:
        raise ValueError(f"COA account not found for code={account_code}")
    return row[0]


def _employee_has_accrual(db, employee_id: int, employee_code: str) -> bool:
    """Check if a salary accrual journal entry already exists for this employee."""
    ref_pattern = f"SAL-{employee_code}-{employee_id}"
    existing = db.query(JournalEntry).filter(
        JournalEntry.reference == ref_pattern
    ).first()
    return existing is not None


def main():
    db = SessionLocal()
    try:
        # Verify required accounts exist
        import sys
        def _out(msg):
            sys.stdout.write(msg + "\n")
            sys.stdout.flush()

        _out("Checking Chart of Accounts ...")
        try:
            expense_account_id = _get_account_id_by_code(db, SALARY_EXPENSE_CODE)
            _out(f"  [OK] Salary Expense (5000) -> account id #{expense_account_id}")
        except ValueError:
            _out("  [FAIL] Salary Expense (5000) NOT found in COA. Aborting.")
            return

        try:
            payable_account_id = _get_account_id_by_code(db, SALARY_PAYABLE_CODE)
            _out(f"  [OK] Salary Payable (2100) -> account id #{payable_account_id}")
        except ValueError:
            _out("  [FAIL] Salary Payable (2100) NOT found in COA. Aborting.")
            return

        # Fetch all employees with a salary (using raw SQL to avoid ORM relationship issues)
        emp_rows = db.execute(
            text("SELECT id, employee_code, salary FROM employees WHERE salary IS NOT NULL AND salary > 0 ORDER BY id")
        ).fetchall()

        _out(f"\nFound {len(emp_rows)} employee(s) with salary set.\n")

        created_count = 0
        skipped_count = 0

        for emp_id, emp_code, emp_salary in emp_rows:
            if _employee_has_accrual(db, emp_id, emp_code):
                _out(f"  [SKIP] #{emp_id} {emp_code}: already has accrual entry, skipping")
                skipped_count += 1
                continue

            amount = Decimal(str(emp_salary))
            journal_ref = f"SAL-{emp_code}-{emp_id}"
            now = datetime.utcnow()

            # Create journal entry
            journal = JournalEntry(
                reference=journal_ref,
                description="Payroll salary accrual (backfill)",
                status="approved",
                date=now,
            )
            db.add(journal)
            db.flush()

            # Add lines: Dr Expense / Cr Salary Payable
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

            # Post to ledger
            post_journal_entry(db, journal)
            db.commit()

            _out(f"  [OK] #{emp_id} {emp_code}: Rs.{amount:,.2f} -> "
                  f"Dr Expense(5000) / Cr Salary Payable(2100)  [{journal_ref}]")
            created_count += 1

        _out(f"\n{'='*50}")
        _out(f"Done. Created: {created_count}  |  Skipped (already existed): {skipped_count}")

    except Exception as exc:
        db.rollback()
        print(f"\nERROR: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
