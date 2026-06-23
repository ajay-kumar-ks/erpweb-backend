from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import BaseModel


class ChartOfAccount(BaseModel):
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_code = Column(String(50), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)
    parent_account_id = Column(Integer, ForeignKey('chart_of_accounts.id'), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    parent = relationship('ChartOfAccount', remote_side=[id], backref='children')


class JournalEntry(BaseModel):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(255), nullable=True)
    description = Column(String(1024), nullable=True)
    status = Column(String(50), default="draft", nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    posted_at = Column(DateTime, nullable=True)

    lines = relationship('JournalLine', back_populates='journal', cascade='all, delete-orphan')


class JournalLine(BaseModel):
    __tablename__ = "journal_lines"

    id = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('chart_of_accounts.id'), nullable=False, index=True)
    memo = Column(String(255), nullable=True)
    debit = Column(Numeric(14, 2), default=0, nullable=False)
    credit = Column(Numeric(14, 2), default=0, nullable=False)

    journal = relationship('JournalEntry', back_populates='lines')


class LedgerEntry(BaseModel):
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('chart_of_accounts.id'), nullable=False, index=True)
    debit = Column(Numeric(14, 2), default=0, nullable=False)
    credit = Column(Numeric(14, 2), default=0, nullable=False)
    posting_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    journal = relationship('JournalEntry')