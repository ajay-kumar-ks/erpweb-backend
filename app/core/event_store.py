from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.base import BaseModel


class EventStore(BaseModel):
    __tablename__ = "event_store"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, primary_key=True)
    event_type = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=False)
    processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
