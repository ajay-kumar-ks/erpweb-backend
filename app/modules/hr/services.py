from app.modules.hr.db_models import Employee, EmployeeStatus, Attendance, LeaveRequest
from app.modules.auth.db_models import User


def format_employee_response(employee: Employee) -> dict:
    """Format an employee record with joined data for API response."""
    result = {
        "id": employee.id,
        "user_id": employee.user_id,
        "employee_code": employee.employee_code,
        "phone": employee.phone,
        "department_id": employee.department_id,
        "role_id": employee.role_id,
        "joining_date": employee.joining_date.isoformat() if employee.joining_date else None,
        "salary": employee.salary,
        "status": employee.status.value if employee.status else None,
        "created_at": employee.created_at.isoformat() if employee.created_at else None,
        "updated_at": employee.updated_at.isoformat() if employee.updated_at else None,
        "user_name": employee.user.full_name if employee.user else None,
        "department_name": employee.department.name if employee.department else None,
        "role_name": employee.role.name if employee.role else None,
    }
    return result


def format_attendance_response(record: Attendance) -> dict:
    """Format an attendance record with joined employee data for API response."""
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "date": record.date.isoformat() if record.date else None,
        "check_in": record.check_in.isoformat() if record.check_in else None,
        "check_out": record.check_out.isoformat() if record.check_out else None,
        "status": record.status.value if record.status else None,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        "employee_name": record.employee.user.full_name if record.employee and record.employee.user else None,
        "employee_code": record.employee.employee_code if record.employee else None,
    }


def format_leave_response(leave: LeaveRequest) -> dict:
    """Format a leave request with joined employee data for API response."""
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "leave_type": leave.leave_type.value if leave.leave_type else None,
        "start_date": leave.start_date.isoformat() if leave.start_date else None,
        "end_date": leave.end_date.isoformat() if leave.end_date else None,
        "reason": leave.reason,
        "status": leave.status.value if leave.status else None,
        "created_at": leave.created_at.isoformat() if leave.created_at else None,
        "updated_at": leave.updated_at.isoformat() if leave.updated_at else None,
        "employee_name": leave.employee.user.full_name if leave.employee and leave.employee.user else None,
        "employee_code": leave.employee.employee_code if leave.employee else None,
    }
