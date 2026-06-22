from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class EventRecord:
    event_id: str
    event_type: str
    tenant_id: int | None
    timestamp: datetime
    payload: dict[str, Any]
