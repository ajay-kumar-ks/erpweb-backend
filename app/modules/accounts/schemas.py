from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class ChartOfAccountCreate(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    parent_account_id: int | None = None
    is_active: bool = True


class ChartOfAccountRead(BaseModel):
    id: int
    account_code: str
    account_name: str
    account_type: str
    parent_account_id: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalLineCreate(BaseModel):
    account_id: int
    memo: str | None = None
    debit: float = Field(0.0, ge=0.0)
    credit: float = Field(0.0, ge=0.0)


class JournalLineRead(BaseModel):
    id: int
    journal_id: int
    account_id: int
    memo: str | None = None
    debit: float
    credit: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalEntryCreate(BaseModel):
    reference: str | None = None
    description: str | None = None
    date: datetime | None = None
    lines: List[JournalLineCreate]


class JournalEntryRead(BaseModel):
    id: int
    reference: str | None = None
    description: str | None = None
    status: str
    date: datetime
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    posted_at: datetime | None = None
    lines: List[JournalLineRead]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LedgerEntryRead(BaseModel):
    id: int
    journal_id: int
    account_id: int
    debit: float
    credit: float
    posting_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JournalStatusUpdate(BaseModel):
    status: str