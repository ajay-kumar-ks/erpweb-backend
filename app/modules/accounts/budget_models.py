import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import BaseModel


class Budget(BaseModel):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    name = Column(String(255), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)


class BudgetLine(BaseModel):
    __tablename__ = "budget_lines"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    account_id = Column(Integer, nullable=False)
    allocated_amount = Column(Numeric(14, 2), nullable=False)
    spent_amount = Column(Numeric(14, 2), default=0, nullable=False)
    consumed_percentage = Column(Numeric(5, 2), default=0, nullable=False)
