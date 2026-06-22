"""Event handlers for the tasks module.

Employee data is now queried directly from the HR module's employees table
via the database. This module is kept for backward compatibility but no longer
maintains an in-memory employee cache.
"""

from typing import Any
from app.core.event_bus import event_bus


_employees: list[dict[str, Any]] = []


def get_employees() -> list[dict[str, Any]]:
    """Return the cached list of employees (deprecated — use direct DB query)."""
    return _employees


def handle_employee_list(payload: list[dict[str, Any]]) -> None:
    """Handler for hr.employee_list event."""
    global _employees
    if isinstance(payload, list):
        _employees = payload


def register_handlers() -> None:
    """Register all event handlers for the tasks module."""
    event_bus.subscribe("hr.employee_list", handle_employee_list)
