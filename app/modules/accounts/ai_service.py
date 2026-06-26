import json
import logging
from decimal import Decimal
from typing import Optional

from openai import OpenAI
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.accounts.models import ChartOfAccount, JournalEntry, LedgerEntry
from app.modules.accounts.ar_models import Customer, Invoice
from app.modules.accounts.ap_models import Vendor, Bill
from app.modules.accounts.transaction_models import Expense, Income
from app.modules.accounts.budget_models import Budget

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None

SYSTEM_PROMPT = """You are an expert financial insights analyst for a small business accounting system.
You will be provided with a compact financial summary.
Your task is to identify practical business insights, cash flow risks, collections or payables pressure, budget warnings, and profit/expense trends.
Do not invent details beyond the data provided. Do not produce raw SQL, code, or tables.
Respond ONLY with valid JSON using the schema below:
{
  "summary": "string",
  "insights": [
    {
      "title": "string",
      "message": "string",
      "severity": "info|positive|warning|critical"
    }
  ]
}
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = settings.ACCOUNTS_OPENROUTER_API_KEY
        if not api_key:
            raise ValueError(
                "ACCOUNTS_OPENROUTER_API_KEY is not configured. Set it in .env."
            )
        _client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - Accounts AI Insights",
            },
        )
    return _client


def _normalize_decimal(value: Optional[Decimal]) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_ai_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl + 1 :].strip()
        if text.endswith("```"):
            text = text[: -3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse AI response as JSON: %s", raw)
        return {
            "summary": "Unable to generate insights from the current data.",
            "insights": [],
        }


def _build_prompt(metrics: dict) -> str:
    lines = ["Financial metrics:"]
    for name, value in metrics.items():
        lines.append(f"- {name}: {value}")
    lines.append("")
    lines.append(
        "Based on only the values above, provide a short business summary and 3-5 high-level insights."
    )
    lines.append("Do not return SQL or code. Do not hallucinate facts beyond the provided metrics.")
    return "\n".join(lines)


def get_financial_insights(db: Session) -> dict:
    total_accounts = db.query(ChartOfAccount).count()
    total_journals = db.query(JournalEntry).count()
    total_ledger_entries = db.query(LedgerEntry).count()
    total_customers = db.query(Customer).count()
    total_vendors = db.query(Vendor).count()
    total_invoices = db.query(Invoice).count()
    unpaid_invoices = db.query(Invoice).filter(Invoice.paid_amount < Invoice.amount).count()
    outstanding_receivables = _normalize_decimal(
        db.query(func.sum(Invoice.amount - Invoice.paid_amount))
        .filter(Invoice.paid_amount < Invoice.amount)
        .scalar()
    )
    total_bills = db.query(Bill).count()
    unpaid_bills = db.query(Bill).filter(Bill.paid_amount < Bill.amount).count()
    outstanding_payables = _normalize_decimal(
        db.query(func.sum(Bill.amount - Bill.paid_amount))
        .filter(Bill.paid_amount < Bill.amount)
        .scalar()
    )
    total_expenses = _normalize_decimal(
        db.query(func.sum(Expense.amount)).scalar()
    )
    total_income = _normalize_decimal(
        db.query(func.sum(Income.amount)).scalar()
    )
    total_budgets = db.query(Budget).count()
    net_cash_flow = total_income - total_expenses

    metrics = {
        "total_accounts": total_accounts,
        "total_journals": total_journals,
        "total_ledger_entries": total_ledger_entries,
        "total_customers": total_customers,
        "total_vendors": total_vendors,
        "total_invoices": total_invoices,
        "unpaid_invoices": unpaid_invoices,
        "outstanding_receivables": f"₹{outstanding_receivables:,.2f}",
        "total_bills": total_bills,
        "unpaid_bills": unpaid_bills,
        "outstanding_payables": f"₹{outstanding_payables:,.2f}",
        "total_income": f"₹{total_income:,.2f}",
        "total_expenses": f"₹{total_expenses:,.2f}",
        "net_cash_flow": f"₹{net_cash_flow:,.2f}",
        "total_budgets": total_budgets,
    }

    prompt = _build_prompt(metrics)
    client = _get_client()
    response = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=700,
    )

    raw = response.choices[0].message.content or ""
    result = _parse_ai_response(raw)

    if not isinstance(result.get("summary"), str):
        result["summary"] = "Could not generate a summary from the current financial data."
    if not isinstance(result.get("insights"), list):
        result["insights"] = []

    normalized_insights = []
    for insight in result.get("insights", []):
        if not isinstance(insight, dict):
            continue
        normalized_insights.append(
            {
                "title": str(insight.get("title", "Insight"))[:120],
                "message": str(insight.get("message", ""))[:1000],
                "severity": str(insight.get("severity", "info"))[:32],
            }
        )

    return {
        "summary": result["summary"],
        "insights": normalized_insights,
    }
