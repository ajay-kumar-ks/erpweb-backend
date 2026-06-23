from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import BaseModel


class Customer(BaseModel):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(512), nullable=True)
    is_active = Column(String(50), default="active", nullable=False)

    invoices = relationship('Invoice', back_populates='customer', cascade='all, delete-orphan')


class Invoice(BaseModel):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    invoice_number = Column(String(255), nullable=False, index=True)
    invoice_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(DateTime, nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    paid_amount = Column(Numeric(14, 2), default=0, nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    description = Column(String(1024), nullable=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id'), nullable=True)

    customer = relationship('Customer', back_populates='invoices')
    payments = relationship('CustomerPayment', back_populates='invoice', cascade='all, delete-orphan')


class CustomerPayment(BaseModel):
    __tablename__ = "customer_payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    payment_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    reference = Column(String(255), nullable=True)
    journal_id = Column(Integer, ForeignKey('journal_entries.id'), nullable=True)

    invoice = relationship('Invoice', back_populates='payments')