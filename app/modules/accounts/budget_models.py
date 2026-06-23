from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.base import BaseModel


class Budget(BaseModel):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(50), default="draft", nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    lines = relationship('BudgetLine', back_populates='budget', cascade='all, delete-orphan')


class BudgetLine(BaseModel):
    __tablename__ = "budget_lines"

    id = Column(Integer, primary_key=True, index=True)
    budget_id = Column(Integer, ForeignKey('budgets.id', ondelete='CASCADE'), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey('chart_of_accounts.id'), nullable=False)
    allocated_amount = Column(Numeric(14, 2), nullable=False)
    spent_amount = Column(Numeric(14, 2), default=0, nullable=False)
    consumed_percentage = Column(Numeric(5, 2), default=0, nullable=False)

    budget = relationship('Budget', back_populates='lines')