import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import BaseModel


class Expense(BaseModel):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    expense_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    account_id = Column(Integer, nullable=False)
    reference = Column(String(255), nullable=True)
    journal_id = Column(Integer, nullable=True)
    status = Column(String(50), default="draft", nullable=False)


class Income(BaseModel):
    __tablename__ = "income"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    description = Column(String(255), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    income_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    account_id = Column(Integer, nullable=False)
    reference = Column(String(255), nullable=True)
    journal_id = Column(Integer, nullable=True)
    status = Column(String(50), default="draft", nullable=False)
