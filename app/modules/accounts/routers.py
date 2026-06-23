from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db, commit_or_rollback
from app.core.event_bus import event_bus
from app.modules.accounts.models import ChartOfAccount, JournalEntry, JournalLine, LedgerEntry
from app.modules.accounts.schemas import (
    ChartOfAccountCreate,
    ChartOfAccountRead,
    JournalEntryCreate,
    JournalEntryRead,
    JournalLineRead,
    JournalStatusUpdate,
    LedgerEntryRead,
)
from app.modules.accounts.services import (
    post_journal_entry,
    validate_journal_lines,
)

from app.modules.accounts.transaction_models import Expense, Income
from app.modules.accounts.transaction_schemas import ExpenseCreate, ExpenseRead, IncomeCreate, IncomeRead
from app.modules.accounts.transaction_services import create_expense_journal, create_income_journal
from app.modules.accounts.ar_models import Customer, Invoice, CustomerPayment
from app.modules.accounts.ar_schemas import (
    CustomerCreate,
    CustomerRead,
    InvoiceCreate,
    InvoiceRead,
    CustomerPaymentCreate,
    CustomerPaymentRead,
)
from app.modules.accounts.ar_services import create_invoice_journal, create_payment_journal
from app.modules.accounts.ap_models import Vendor, Bill, VendorPayment
from app.modules.accounts.ap_schemas import (
    VendorCreate,
    VendorRead,
    BillCreate,
    BillRead,
    VendorPaymentCreate,
    VendorPaymentRead,
)
from app.modules.accounts.ap_services import create_bill_journal, create_vendor_payment_journal
from app.modules.accounts.budget_models import Budget, BudgetLine
from app.modules.accounts.budget_schemas import BudgetCreate, BudgetRead, BudgetLineCreate, BudgetLineRead
from app.modules.accounts.budget_services import calculate_budget_consumption
from app.modules.accounts.reports_services import TrialBalance, ProfitLoss, BalanceSheet
from app.modules.accounts.reports_schemas import TrialBalanceReport, ProfitLossReport, BalanceSheetReport

router = APIRouter()


@router.get("/")
async def health(db: Session = Depends(get_db)):
    return {
        "status": "Accounts module ready",
        "total_accounts": db.query(ChartOfAccount).count(),
        "total_journals": db.query(JournalEntry).count(),
        "total_ledger_entries": db.query(LedgerEntry).count(),
    }


@router.post("/coa", response_model=ChartOfAccountRead)
def create_coa_entry(
    data: ChartOfAccountCreate,
    db: Session = Depends(get_db),
):
    account = ChartOfAccount(
        account_code=data.account_code,
        account_name=data.account_name,
        account_type=data.account_type,
        parent_account_id=data.parent_account_id,
        is_active=data.is_active,
    )
    db.add(account)
    commit_or_rollback(db)
    db.refresh(account)
    return account


@router.get("/coa", response_model=List[ChartOfAccountRead])
def list_coa(db: Session = Depends(get_db)):
    return db.query(ChartOfAccount).order_by(ChartOfAccount.account_code).all()


@router.post("/journals", response_model=JournalEntryRead)
def create_journal_entry(
    data: JournalEntryCreate,
    db: Session = Depends(get_db),
):
    account_ids = [line.account_id for line in data.lines]
    valid_accounts = {id for (id,) in db.query(ChartOfAccount.id).filter(ChartOfAccount.id.in_(account_ids))}

    if set(account_ids) != valid_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more journal lines reference accounts that do not exist.",
        )

    journal = JournalEntry(
        reference=data.reference,
        description=data.description,
        status="draft",
        date=data.date or datetime.utcnow(),
    )
    db.add(journal)
    db.flush()

    lines = []
    for line_data in data.lines:
        journal_line = JournalLine(
            journal_id=journal.id,
            account_id=line_data.account_id,
            memo=line_data.memo,
            debit=Decimal(str(line_data.debit)),
            credit=Decimal(str(line_data.credit)),
        )
        db.add(journal_line)
        lines.append(journal_line)

    validate_journal_lines(lines)

    commit_or_rollback(db)
    db.refresh(journal)
    journal.lines = lines
    return journal


@router.get("/journals", response_model=List[JournalEntryRead])
def list_journal_entries(db: Session = Depends(get_db)):
    journals = db.query(JournalEntry).order_by(JournalEntry.date.desc()).all()
    # Eager-load lines for each journal for schema serialization
    journal_ids = [j.id for j in journals]
    if journal_ids:
        all_lines = db.query(JournalLine).filter(
            JournalLine.journal_id.in_(journal_ids)
        ).all()
        lines_by_journal = {}
        for line in all_lines:
            lines_by_journal.setdefault(line.journal_id, []).append(line)
        for j in journals:
            j.lines = lines_by_journal.get(j.id, [])
    return journals


def _load_journal_lines(db: Session, journal: JournalEntry) -> None:
    """Helper to eager-load lines on a journal entry for schema serialization."""
    journal.lines = db.query(JournalLine).filter(JournalLine.journal_id == journal.id).all()


@router.post("/journals/{journal_id}/submit", response_model=JournalEntryRead)
def submit_journal_entry(
    journal_id: int,
    db: Session = Depends(get_db),
):
    journal = db.query(JournalEntry).filter(JournalEntry.id == journal_id).first()
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    if journal.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft journals can be submitted.")
    journal.status = "submitted"
    journal.submitted_at = datetime.utcnow()
    commit_or_rollback(db)
    db.refresh(journal)
    _load_journal_lines(db, journal)
    return journal


@router.post("/journals/{journal_id}/approve", response_model=JournalEntryRead)
def approve_journal_entry(
    journal_id: int,
    db: Session = Depends(get_db),
):
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == journal_id)
        .first()
    )
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    if journal.status != "submitted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only submitted journals can be approved.")
    journal.status = "approved"
    journal.approved_at = datetime.utcnow()
    commit_or_rollback(db)
    db.refresh(journal)
    _load_journal_lines(db, journal)
    return journal


@router.post("/journals/{journal_id}/post", response_model=JournalEntryRead)
def post_journal_entry_endpoint(
    journal_id: int,
    db: Session = Depends(get_db),
):
    journal = (
        db.query(JournalEntry)
        .filter(JournalEntry.id == journal_id)
        .first()
    )
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")

    try:
        posted = post_journal_entry(db, journal)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _load_journal_lines(db, posted)
    return posted


@router.get("/ledger", response_model=List[LedgerEntryRead])
def list_ledger_entries(db: Session = Depends(get_db)):
    return db.query(LedgerEntry).order_by(LedgerEntry.posting_date.desc()).all()


@router.get("/journals/{journal_id}", response_model=JournalEntryRead)
def get_journal_entry(journal_id: int, db: Session = Depends(get_db)):
    journal = db.query(JournalEntry).filter(JournalEntry.id == journal_id).first()
    if not journal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found.")
    _load_journal_lines(db, journal)
    return journal


# ===== TRANSACTION LAYER =====


@router.post("/expenses", response_model=ExpenseRead)
def create_expense(
    data: ExpenseCreate,
    db: Session = Depends(get_db),
):
    expense = Expense(
        description=data.description,
        amount=Decimal(str(data.amount)),
        expense_date=data.expense_date or datetime.utcnow(),
        account_id=data.account_id,
        reference=data.reference,
        status="draft",
    )
    db.add(expense)
    commit_or_rollback(db)
    db.refresh(expense)

    journal = create_expense_journal(db, expense)
    expense.journal_id = journal.id
    commit_or_rollback(db)
    db.refresh(expense)

    event_bus.publish(
        "expense.created",
        {
            "expense_id": expense.id,
            "amount": float(expense.amount),
            "account_id": expense.account_id,
            "journal_id": journal.id,
        },
    )

    return expense


@router.get("/expenses", response_model=List[ExpenseRead])
def list_expenses(db: Session = Depends(get_db)):
    return db.query(Expense).all()


@router.post("/income", response_model=IncomeRead)
def create_income(
    data: IncomeCreate,
    db: Session = Depends(get_db),
):
    income = Income(
        description=data.description,
        amount=Decimal(str(data.amount)),
        income_date=data.income_date or datetime.utcnow(),
        account_id=data.account_id,
        reference=data.reference,
        status="draft",
    )
    db.add(income)
    commit_or_rollback(db)
    db.refresh(income)

    journal = create_income_journal(db, income)
    income.journal_id = journal.id
    commit_or_rollback(db)
    db.refresh(income)

    event_bus.publish(
        "income.created",
        {
            "income_id": income.id,
            "amount": float(income.amount),
            "account_id": income.account_id,
            "journal_id": journal.id,
        },
    )

    return income


@router.get("/income", response_model=List[IncomeRead])
def list_income(db: Session = Depends(get_db)):
    return db.query(Income).all()


# ===== ACCOUNTS RECEIVABLE =====


@router.post("/customers", response_model=CustomerRead)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
):
    customer = Customer(
        name=data.name,
        email=data.email,
        phone=data.phone,
        address=data.address,
        is_active=data.is_active,
    )
    db.add(customer)
    commit_or_rollback(db)
    db.refresh(customer)
    return customer


@router.get("/customers", response_model=List[CustomerRead])
def list_customers(db: Session = Depends(get_db)):
    return db.query(Customer).all()


@router.post("/invoices", response_model=InvoiceRead)
def create_invoice(
    data: InvoiceCreate,
    db: Session = Depends(get_db),
):
    invoice = Invoice(
        customer_id=data.customer_id,
        invoice_number=data.invoice_number,
        invoice_date=data.invoice_date or datetime.utcnow(),
        due_date=data.due_date,
        amount=Decimal(str(data.amount)),
        paid_amount=Decimal("0"),
        status="draft",
        description=data.description,
    )
    db.add(invoice)
    commit_or_rollback(db)
    db.refresh(invoice)

    journal = create_invoice_journal(db, invoice)
    invoice.journal_id = journal.id
    commit_or_rollback(db)
    db.refresh(invoice)

    return invoice


@router.get("/invoices", response_model=List[InvoiceRead])
def list_invoices(db: Session = Depends(get_db)):
    return db.query(Invoice).all()


@router.post("/invoices/{invoice_id}/payments", response_model=CustomerPaymentRead)
def create_customer_payment(
    invoice_id: int,
    data: CustomerPaymentCreate,
    db: Session = Depends(get_db),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    payment = CustomerPayment(
        invoice_id=invoice_id,
        payment_date=data.payment_date or datetime.utcnow(),
        amount=Decimal(str(data.amount)),
        reference=data.reference,
    )
    db.add(payment)
    commit_or_rollback(db)
    db.refresh(payment)
    journal = create_payment_journal(db, payment, invoice)
    payment.journal_id = journal.id

    invoice.paid_amount += Decimal(str(data.amount))
    if invoice.paid_amount >= invoice.amount:
        invoice.status = "paid"

    commit_or_rollback(db)
    db.refresh(payment)

    return payment


# ===== ACCOUNTS PAYABLE =====


@router.post("/vendors", response_model=VendorRead)
def create_vendor(
    data: VendorCreate,
    db: Session = Depends(get_db),
):
    vendor = Vendor(
        name=data.name,
        email=data.email,
        phone=data.phone,
        address=data.address,
        is_active=data.is_active,
    )
    db.add(vendor)
    commit_or_rollback(db)
    db.refresh(vendor)
    return vendor


@router.get("/vendors", response_model=List[VendorRead])
def list_vendors(db: Session = Depends(get_db)):
    return db.query(Vendor).all()


@router.post("/bills", response_model=BillRead)
def create_bill(
    data: BillCreate,
    db: Session = Depends(get_db),
):
    bill = Bill(
        vendor_id=data.vendor_id,
        bill_number=data.bill_number,
        bill_date=data.bill_date or datetime.utcnow(),
        due_date=data.due_date,
        amount=Decimal(str(data.amount)),
        paid_amount=Decimal("0"),
        status="draft",
        description=data.description,
    )
    db.add(bill)
    commit_or_rollback(db)
    db.refresh(bill)
    journal = create_bill_journal(db, bill)
    bill.journal_id = journal.id
    commit_or_rollback(db)
    db.refresh(bill)

    return bill


@router.get("/bills", response_model=List[BillRead])
def list_bills(db: Session = Depends(get_db)):
    return db.query(Bill).all()


@router.post("/bills/{bill_id}/payments", response_model=VendorPaymentRead)
def create_vendor_payment(
    bill_id: int,
    data: VendorPaymentCreate,
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found.")
    payment = VendorPayment(
        bill_id=bill_id,
        payment_date=data.payment_date or datetime.utcnow(),
        amount=Decimal(str(data.amount)),
        reference=data.reference,
    )
    db.add(payment)
    commit_or_rollback(db)
    db.refresh(payment)
    journal = create_vendor_payment_journal(db, payment, bill)
    payment.journal_id = journal.id

    bill.paid_amount += Decimal(str(data.amount))
    if bill.paid_amount >= bill.amount:
        bill.status = "paid"

    commit_or_rollback(db)
    db.refresh(payment)

    return payment


# ===== BUDGET MANAGEMENT =====


@router.post("/budgets", response_model=BudgetRead)
def create_budget(
    data: BudgetCreate,
    db: Session = Depends(get_db),
):
    budget = Budget(
        name=data.name,
        fiscal_year=data.fiscal_year,
        total_amount=Decimal(str(data.total_amount)),
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(budget)
    commit_or_rollback(db)
    db.refresh(budget)
    event_bus.publish(
        "budget.created",
        {
            "budget_id": budget.id,
            "name": budget.name,
            "fiscal_year": budget.fiscal_year,
            "total_amount": float(budget.total_amount),
        },
    )

    return budget


@router.get("/budgets", response_model=List[BudgetRead])
def list_budgets(db: Session = Depends(get_db)):
    return db.query(Budget).all()


@router.post("/budgets/{budget_id}/lines", response_model=BudgetLineRead)
def create_budget_line(
    budget_id: int,
    data: BudgetLineCreate,
    db: Session = Depends(get_db),
):
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found.")
    budget_line = BudgetLine(
        budget_id=budget_id,
        account_id=data.account_id,
        allocated_amount=Decimal(str(data.allocated_amount)),
        spent_amount=Decimal("0"),
        consumed_percentage=Decimal("0"),
    )
    db.add(budget_line)
    commit_or_rollback(db)
    db.refresh(budget_line)

    calculate_budget_consumption(db, budget_line)

    return budget_line


@router.get("/budgets/{budget_id}/lines", response_model=List[BudgetLineRead])
def list_budget_lines(
    budget_id: int,
    db: Session = Depends(get_db),
):
    return db.query(BudgetLine).filter(BudgetLine.budget_id == budget_id).all()


# ===== FINANCIAL REPORTS =====


@router.get("/reports/trial-balance", response_model=TrialBalanceReport)
def trial_balance_report(db: Session = Depends(get_db)):
    tb = TrialBalance()
    return tb.generate(db)


@router.get("/reports/profit-loss", response_model=ProfitLossReport)
def profit_loss_report(db: Session = Depends(get_db)):
    pl = ProfitLoss()
    return pl.generate(db)


@router.get("/reports/balance-sheet", response_model=BalanceSheetReport)
def balance_sheet_report(db: Session = Depends(get_db)):
    bs = BalanceSheet()
    return bs.generate(db)
