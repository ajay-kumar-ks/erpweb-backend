import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    description: str
    amount: float = Field(gt=0)
    expense_date: datetime | None = None
    account_id: int
    reference: str | None = None


class ExpenseRead(BaseModel):
    id: int
    tenant_id: uuid.UUID
    description: str
    amount: float
    expense_date: datetime
    account_id: int
    reference: str | None
    journal_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncomeCreate(BaseModel):
    description: str
    amount: float = Field(gt=0)
    income_date: datetime | None = None
    account_id: int
    reference: str | None = None


class IncomeRead(BaseModel):
    id: int
    tenant_id: uuid.UUID
    description: str
    amount: float
    income_date: datetime
    account_id: int
    reference: str | None
    journal_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
