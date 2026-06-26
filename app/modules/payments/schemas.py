from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class CreateOrderRequest(BaseModel):
    amount: int  # in paise
    currency: str = "INR"
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[dict] = None


class CreateOrderResponse(BaseModel):
    razorpay_order_id: str
    amount: int
    currency: str
    key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class FailPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None


class VerifyPaymentResponse(BaseModel):
    success: bool
    payment_id: str
    status: str


class PaymentSchema(BaseModel):
    id: str
    razorpay_order_id: str
    razorpay_payment_id: Optional[str] = None
    amount: int
    currency: str
    status: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    description: Optional[str] = None
    receipt_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    payments: list[PaymentSchema]
    total: int
