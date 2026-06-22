from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.modules.hr.db_models import EmployeeStatus, AttendanceStatus, LeaveType, LeaveStatus


# --- HR User Management ---

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str
    password: str
    is_admin: bool = False


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    is_admin: bool = False

    model_config = {"from_attributes": True}


# --- Employee ---

class EmployeeCreate(BaseModel):
    user_id: int
    employee_code: Optional[str] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    joining_date: Optional[date] = None
    salary: Optional[float] = None
    status: EmployeeStatus = EmployeeStatus.ACTIVE


class EmployeeUpdate(BaseModel):
    user_id: Optional[int] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    joining_date: Optional[date] = None
    salary: Optional[float] = None
    status: Optional[EmployeeStatus] = None


class EmployeeResponse(BaseModel):
    id: int
    user_id: int
    employee_code: str
    phone: Optional[str] = None
    department_id: Optional[int] = None
    role_id: Optional[int] = None
    joining_date: Optional[date] = None
    salary: Optional[float] = None
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime

    # Joined data
    user_name: Optional[str] = None
    department_name: Optional[str] = None
    role_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    employees: list[EmployeeResponse]
    total: int


# --- Role ---

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Department ---

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Attendance ---

class AttendanceCreate(BaseModel):
    employee_id: int
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: AttendanceStatus = AttendanceStatus.PRESENT


class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    status: AttendanceStatus
    created_at: datetime
    updated_at: datetime

    # Joined data
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None

    model_config = {"from_attributes": True}


class AttendanceListResponse(BaseModel):
    attendance_records: list[AttendanceResponse]
    total: int


# --- Leave ---

class LeaveCreate(BaseModel):
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class MyLeaveCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveStatusUpdate(BaseModel):
    status: LeaveStatus


class LeaveResponse(BaseModel):
    id: int
    employee_id: int
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: LeaveStatus
    created_at: datetime
    updated_at: datetime

    # Joined data
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None

    model_config = {"from_attributes": True}
