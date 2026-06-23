import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    is_active: str = "active"


class VendorRead(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    address: str | None
    is_active: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BillCreate(BaseModel):
    vendor_id: int
    bill_number: str
    bill_date: datetime | None = None
    due_date: datetime | None = None
    amount: float = Field(gt=0)
    description: str | None = None


class BillRead(BaseModel):
    id: int
    vendor_id: int
    bill_number: str
    bill_date: datetime
    due_date: datetime | None
    amount: float
    paid_amount: float
    status: str
    description: str | None
    journal_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VendorPaymentCreate(BaseModel):
    payment_date: datetime | None = None
    amount: float = Field(gt=0)
    reference: str | None = None


class VendorPaymentRead(BaseModel):
    id: int
    bill_id: int
    payment_date: datetime
    amount: float
    reference: str | None
    journal_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}