from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Float, Enum as SAEnum
from sqlalchemy.sql import func
from app.core.base import Base
import enum


class PaymentStatus(str, enum.Enum):
    CREATED = "created"
    ATTEMPTED = "attempted"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(Base):
    """Stores all Razorpay payment transactions."""
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True)
    razorpay_order_id = Column(String, unique=True, nullable=False, index=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)

    # Payment details
    amount = Column(Integer, nullable=False)  # in paise (smallest currency unit)
    currency = Column(String, default="INR")
    status = Column(String, default=PaymentStatus.CREATED.value, index=True)

    # Customer info
    customer_name = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    customer_phone = Column(String, nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    notes = Column(JSON, default=dict, nullable=False)
    receipt_id = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
