from decimal import Decimal
from datetime import datetime
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from app.modules.accounts.models import LedgerEntry, ChartOfAccount, JournalEntry


class TrialBalance:
    def __init__(self):
        # single-company mode: no tenant scoping
        self.accounts: dict = {}
        self.total_debit = Decimal("0")
        self.total_credit = Decimal("0")
        self.is_balanced = False

    def generate(self, db: Session) -> dict:
        """Generate trial balance from ledger entries."""
        ledger_data = (
            db.query(
                LedgerEntry.account_id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
                func.sum(LedgerEntry.debit).label("total_debit"),
                func.sum(LedgerEntry.credit).label("total_credit"),
            )
            .select_from(LedgerEntry)
            .join(
                ChartOfAccount,
                and_(
                    ChartOfAccount.id == LedgerEntry.account_id,
                ),
            )
            .group_by(
                LedgerEntry.account_id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
            )
            .group_by(
                LedgerEntry.account_id,
                ChartOfAccount.account_code,
                ChartOfAccount.account_name,
                ChartOfAccount.account_type,
            )
            .all()
        )

        for account_id, code, name, acc_type, debit, credit in ledger_data:
            debit = debit or Decimal("0")
            credit = credit or Decimal("0")

            self.accounts[account_id] = {
                "account_id": account_id,
                "account_code": code,
                "account_name": name,
                "account_type": acc_type,
                "debit": float(debit),
                "credit": float(credit),
            }

            self.total_debit += debit
            self.total_credit += credit

        self.is_balanced = self.total_debit == self.total_credit

        return {
            "accounts": list(self.accounts.values()),
            "total_debit": float(self.total_debit),
            "total_credit": float(self.total_credit),
            "is_balanced": self.is_balanced,
            "generated_at": datetime.utcnow().isoformat(),
        }


class ProfitLoss:
    def __init__(self):
        self.revenue = Decimal("0")
        self.expenses = Decimal("0")
        self.net_profit = Decimal("0")

    def generate(self, db: Session) -> dict:
        """Generate P&L statement from ledger entries."""
        revenue_data = (
            db.query(func.sum(LedgerEntry.credit).label("total_revenue"))
            .select_from(LedgerEntry)
            .join(ChartOfAccount, ChartOfAccount.id == LedgerEntry.account_id)
            .filter(ChartOfAccount.account_type == "Revenue")
            .first()
        )

        expense_data = (
            db.query(func.sum(LedgerEntry.debit).label("total_expense"))
            .select_from(LedgerEntry)
            .join(ChartOfAccount, ChartOfAccount.id == LedgerEntry.account_id)
            .filter(ChartOfAccount.account_type == "Expense")
            .first()
        )

        self.revenue = getattr(revenue_data, "total_revenue", None) or Decimal("0")
        expenses = getattr(expense_data, "total_expense", None) or Decimal("0")
        self.expenses = expenses
        self.net_profit = self.revenue - self.expenses

        return {
            "revenue": float(self.revenue),
            "expenses": float(self.expenses),
            "net_profit": float(self.net_profit),
            "generated_at": datetime.utcnow().isoformat(),
        }


class BalanceSheet:
    def __init__(self):
        self.assets = Decimal("0")
        self.liabilities = Decimal("0")
        self.equity = Decimal("0")

    def generate(self, db: Session) -> dict:
        """Generate balance sheet from ledger entries."""
        asset_data = (
            db.query(func.sum(LedgerEntry.debit).label("total_assets"))
            .select_from(LedgerEntry)
            .join(ChartOfAccount, ChartOfAccount.id == LedgerEntry.account_id)
            .filter(ChartOfAccount.account_type == "Asset")
            .first()
        )

        liability_data = (
            db.query(func.sum(LedgerEntry.credit).label("total_liabilities"))
            .select_from(LedgerEntry)
            .join(ChartOfAccount, ChartOfAccount.id == LedgerEntry.account_id)
            .filter(ChartOfAccount.account_type == "Liability")
            .first()
        )

        equity_data = (
            db.query(func.sum(LedgerEntry.credit).label("total_equity"))
            .select_from(LedgerEntry)
            .join(ChartOfAccount, ChartOfAccount.id == LedgerEntry.account_id)
            .filter(ChartOfAccount.account_type == "Equity")
            .first()
        )

        self.assets = getattr(asset_data, "total_assets", None) or Decimal("0")
        self.liabilities = getattr(liability_data, "total_liabilities", None) or Decimal("0")
        self.equity = getattr(equity_data, "total_equity", None) or Decimal("0")

        is_balanced = self.assets == (self.liabilities + self.equity)

        return {
            "assets": float(self.assets),
            "liabilities": float(self.liabilities),
            "equity": float(self.equity),
            "is_balanced": is_balanced,
            "generated_at": datetime.utcnow().isoformat(),
        }