from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import BaseModel


class Vendor(BaseModel):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(512), nullable=True)
    is_active = Column(String(50), default="active", nullable=False)

    bills = relationship('Bill', back_populates='vendor', cascade='all, delete-orphan')


class Bill(BaseModel):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False)
    bill_number = Column(String(255), nullable=False, index=True)
    bill_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(DateTime, nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    paid_amount = Column(Numeric(14, 2), default=0, nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    description = Column(String(1024), nullable=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id'), nullable=True)

    vendor = relationship('Vendor', back_populates='bills')
    payments = relationship('VendorPayment', back_populates='bill', cascade='all, delete-orphan')


class VendorPayment(BaseModel):
    __tablename__ = "vendor_payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey('bills.id', ondelete='CASCADE'), nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    reference = Column(String(255), nullable=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id'), nullable=True)

    bill = relationship('Bill', back_populates='payments')