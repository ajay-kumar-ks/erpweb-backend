from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.base import BaseModel
import enum


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    RESIGNED = "Resigned"


class Role(BaseModel):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(500), nullable=True)

    employees = relationship("Employee", back_populates="role")

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class Department(BaseModel):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(String(500), nullable=True)

    employees = relationship("Employee", back_populates="department")

    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name})>"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "Present"
    ABSENT = "Absent"
    HALF_DAY = "Half Day"
    LEAVE = "Leave"


class Attendance(BaseModel):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    status = Column(
        Enum(AttendanceStatus),
        default=AttendanceStatus.PRESENT,
        nullable=False,
    )

    employee = relationship("Employee")

    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_employee_attendance_date"),)

    def __repr__(self):
        return f"<Attendance(id={self.id}, employee_id={self.employee_id}, date={self.date}, status={self.status})>"


class LeaveType(str, enum.Enum):
    CASUAL = "Casual Leave"
    SICK = "Sick Leave"
    EMERGENCY = "Emergency Leave"


class LeaveStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class LeaveRequest(BaseModel):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type = Column(Enum(LeaveType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(1000), nullable=True)
    status = Column(
        Enum(LeaveStatus),
        default=LeaveStatus.PENDING,
        nullable=False,
    )

    employee = relationship("Employee")

    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, employee_id={self.employee_id}, type={self.leave_type}, status={self.status})>"


class Employee(BaseModel):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("auth_users.id"), nullable=False)
    employee_code = Column(String(50), unique=True, nullable=False)
    phone = Column(String(50), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    joining_date = Column(Date, nullable=True)
    salary = Column(Float, nullable=True)
    status = Column(
        Enum(EmployeeStatus),
        default=EmployeeStatus.ACTIVE,
        nullable=False,
    )

    user = relationship("User")
    role = relationship("Role", back_populates="employees")
    department = relationship("Department", back_populates="employees")

    def __repr__(self):
        return f"<Employee(id={self.id}, code={self.employee_code}, status={self.status})>"
