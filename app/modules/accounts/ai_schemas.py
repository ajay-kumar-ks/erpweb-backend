from pydantic import BaseModel
from typing import List, Literal


class InsightItem(BaseModel):
    title: str
    message: str
    severity: Literal['info', 'positive', 'warning', 'critical']


class FinancialInsightsResponse(BaseModel):
    summary: str
    insights: List[InsightItem]
