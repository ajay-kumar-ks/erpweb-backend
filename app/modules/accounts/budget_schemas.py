import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    name: str
    fiscal_year: int
    total_amount: float = Field(gt=0)
    start_date: datetime
    end_date: datetime
    status: str = "draft"


class BudgetRead(BaseModel):
    id: int
    tenant_id: uuid.UUID
    name: str
    fiscal_year: int
    total_amount: float
    status: str
    start_date: datetime
    end_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetLineCreate(BaseModel):
    account_id: int
    allocated_amount: float = Field(gt=0)


class BudgetLineRead(BaseModel):
    id: int
    budget_id: int
    tenant_id: uuid.UUID
    account_id: int
    allocated_amount: float
    spent_amount: float
    consumed_percentage: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
