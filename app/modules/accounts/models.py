import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "accounts_tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(50), default="active", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class ChartOfAccount(BaseModel):
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    account_code = Column(String(50), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)
    parent_account_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class JournalEntry(BaseModel):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    reference = Column(String(255), nullable=True)
    description = Column(String(1024), nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)


class JournalLine(BaseModel):
    __tablename__ = "journal_lines"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    journal_id = Column(Integer, nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    memo = Column(String(255), nullable=True)
    debit = Column(Numeric(14, 2), default=0, nullable=False)
    credit = Column(Numeric(14, 2), default=0, nullable=False)


class LedgerEntry(BaseModel):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    journal_id = Column(Integer, nullable=False, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    debit = Column(Numeric(14, 2), default=0, nullable=False)
    credit = Column(Numeric(14, 2), default=0, nullable=False)
    posting_date = Column(DateTime, default=datetime.utcnow, nullable=False)
