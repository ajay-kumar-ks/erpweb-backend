from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import date
from fastapi import HTTPException, status
from app.modules.hr.db_models import Employee, Role, Department, EmployeeStatus, Attendance, AttendanceStatus, LeaveRequest, LeaveType, LeaveStatus
from app.modules.auth.db_models import User
from app.modules.auth.utils import get_password_hash
from app.modules.hr.schemas import EmployeeCreate, EmployeeUpdate, AttendanceCreate, LeaveCreate, LeaveStatusUpdate, UserCreate


def get_employees(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status_filter: EmployeeStatus | None = None,
    search: str | None = None,
    department_id: int | None = None,
) -> tuple[list[Employee], int]:
    query = db.query(Employee)

    if status_filter:
        query = query.filter(Employee.status == status_filter)

    if search:
        query = query.join(User, Employee.user_id == User.id).filter(
            or_(
                Employee.employee_code.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
            )
        )

    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)

    total = query.count()
    employees = query.order_by(Employee.id.desc()).offset(skip).limit(limit).all()
    return employees, total


def get_employee(db: Session, employee_id: int) -> Employee | None:
    return db.query(Employee).filter(Employee.id == employee_id).first()


def get_employee_by_user_id(db: Session, user_id: int) -> Employee | None:
    return db.query(Employee).filter(Employee.user_id == user_id).first()


def generate_employee_code(db: Session) -> str:
    last_employee = db.query(Employee).order_by(Employee.id.desc()).first()
    if last_employee:
        try:
            last_num = int(last_employee.employee_code.replace("EMP", ""))
            return f"EMP{last_num + 1:04d}"
        except (ValueError, AttributeError):
            pass
    return "EMP0001"


def create_employee(db: Session, data: EmployeeCreate) -> Employee:
    # Validate user exists
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {data.user_id} not found",
        )

    # Check if user is already linked to an employee
    existing = get_employee_by_user_id(db, data.user_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User id {data.user_id} is already linked to employee {existing.employee_code}",
        )

    # Validate department if provided
    if data.department_id:
        dept = db.query(Department).filter(Department.id == data.department_id).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {data.department_id} not found",
            )

    # Validate role if provided
    if data.role_id:
        role = db.query(Role).filter(Role.id == data.role_id).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id {data.role_id} not found",
            )

    employee_code = data.employee_code or generate_employee_code(db)

    employee = Employee(
        user_id=data.user_id,
        employee_code=employee_code,
        phone=data.phone,
        department_id=data.department_id,
        role_id=data.role_id,
        joining_date=data.joining_date,
        salary=data.salary,
        status=data.status,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def update_employee(db: Session, employee_id: int, data: EmployeeUpdate) -> Employee | None:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Validate user_id if changed
    if "user_id" in update_data and update_data["user_id"] != employee.user_id:
        user = db.query(User).filter(User.id == update_data["user_id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {update_data['user_id']} not found",
            )
        existing = get_employee_by_user_id(db, update_data["user_id"])
        if existing and existing.id != employee_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User id {update_data['user_id']} is already linked to another employee",
            )

    # Validate department if provided
    if "department_id" in update_data and update_data["department_id"] is not None:
        dept = db.query(Department).filter(Department.id == update_data["department_id"]).first()
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {update_data['department_id']} not found",
            )

    # Validate role if provided
    if "role_id" in update_data and update_data["role_id"] is not None:
        role = db.query(Role).filter(Role.id == update_data["role_id"]).first()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id {update_data['role_id']} not found",
            )

    for key, value in update_data.items():
        setattr(employee, key, value)

    db.commit()
    db.refresh(employee)
    return employee


def delete_employee(db: Session, employee_id: int) -> bool:
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return False
    db.delete(employee)
    db.commit()
    return True


# ──────────────────────────────────────────────
# Role CRUD
# ──────────────────────────────────────────────


def get_roles(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


def get_role(db: Session, role_id: int) -> Role | None:
    return db.query(Role).filter(Role.id == role_id).first()


def create_role(db: Session, data) -> Role:
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{data.name}' already exists",
        )
    role = Role(name=data.name, description=data.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role_id: int, data) -> Role | None:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return None

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != role.name:
        existing = db.query(Role).filter(Role.name == update_data["name"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{update_data['name']}' already exists",
            )

    for key, value in update_data.items():
        setattr(role, key, value)

    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: int) -> bool:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        return False

    # Check if any employees reference this role
    employees_with_role = db.query(Employee).filter(Employee.role_id == role_id).count()
    if employees_with_role > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role: {employees_with_role} employee(s) are assigned to it",
        )

    db.delete(role)
    db.commit()
    return True


# ──────────────────────────────────────────────
# Department CRUD
# ──────────────────────────────────────────────


def get_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name).all()


def get_department(db: Session, department_id: int) -> Department | None:
    return db.query(Department).filter(Department.id == department_id).first()


def create_department(db: Session, data) -> Department:
    existing = db.query(Department).filter(Department.name == data.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department '{data.name}' already exists",
        )
    department = Department(name=data.name, description=data.description)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def update_department(db: Session, department_id: int, data) -> Department | None:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        return None

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != department.name:
        existing = db.query(Department).filter(Department.name == update_data["name"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department '{update_data['name']}' already exists",
            )

    for key, value in update_data.items():
        setattr(department, key, value)

    db.commit()
    db.refresh(department)
    return department


def delete_department(db: Session, department_id: int) -> bool:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        return False

    # Check if any employees reference this department
    employees_in_dept = db.query(Employee).filter(Employee.department_id == department_id).count()
    if employees_in_dept > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete department: {employees_in_dept} employee(s) are assigned to it",
        )

    db.delete(department)
    db.commit()
    return True


# ──────────────────────────────────────────────
# Attendance CRUD
# ──────────────────────────────────────────────


def get_attendance(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    employee_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Attendance], int]:
    query = db.query(Attendance)

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)

    if date_from:
        query = query.filter(Attendance.date >= date_from)

    if date_to:
        query = query.filter(Attendance.date <= date_to)

    total = query.count()
    records = query.order_by(Attendance.date.desc(), Attendance.id.desc()).offset(skip).limit(limit).all()
    return records, total


def mark_attendance(db: Session, data: AttendanceCreate) -> Attendance:
    # Validate employee exists
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {data.employee_id} not found",
        )

    # Check for duplicate attendance on same date
    existing = db.query(Attendance).filter(
        Attendance.employee_id == data.employee_id,
        Attendance.date == data.date,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance already exists for employee {data.employee_id} on {data.date}",
        )

    record = Attendance(
        employee_id=data.employee_id,
        date=data.date,
        check_in=data.check_in,
        check_out=data.check_out,
        status=data.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_attendance_by_employee(db: Session, employee_id: int) -> list[Attendance]:
    return db.query(Attendance).filter(Attendance.employee_id == employee_id).order_by(Attendance.date.desc()).all()


# ──────────────────────────────────────────────
# Leave CRUD
# ──────────────────────────────────────────────


def get_leave_requests(db: Session, skip: int = 0, limit: int = 100) -> tuple[list[LeaveRequest], int]:
    query = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    total = query.count()
    leaves = query.offset(skip).limit(limit).all()
    return leaves, total


def create_leave_request(db: Session, data: LeaveCreate) -> LeaveRequest:
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {data.employee_id} not found",
        )

    if data.start_date > data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date",
        )

    leave = LeaveRequest(
        employee_id=data.employee_id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


def update_leave_status(db: Session, leave_id: int, data: LeaveStatusUpdate) -> LeaveRequest | None:
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        return None

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave request is already {leave.status.value}. Only pending requests can be updated",
        )

    leave.status = data.status
    db.commit()
    db.refresh(leave)
    return leave


# ──────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# HR User Management
# ──────────────────────────────────────────────


def get_hr_users(db: Session) -> list[User]:
    """Get all auth users."""
    return db.query(User).order_by(User.username).all()


def create_hr_user(db: Session, data: UserCreate) -> User:
    """Create a new auth user from HR module."""
    existing_username = db.query(User).filter(User.username == data.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{data.username}' already exists",
        )

    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{data.email}' already exists",
        )

    user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        disabled=False,
        is_admin=data.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_hr_user(db: Session, user_id: int, data) -> User | None:
    """Update an existing auth user from HR module."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Check email uniqueness if changed
    if "email" in update_data and update_data["email"] != user.email:
        existing_email = db.query(User).filter(User.email == update_data["email"]).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{update_data['email']}' already exists",
            )

    # Hash password if provided
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_hr_user(db: Session, user_id: int) -> bool:
    """Delete an auth user from HR module."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False

    # Check if user is linked to any employee
    linked_employee = db.query(Employee).filter(Employee.user_id == user_id).first()
    if linked_employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete user: user is linked to employee '{linked_employee.employee_code}'. Remove the employee record first.",
        )

    db.delete(user)
    db.commit()
    return True


# ──────────────────────────────────────────────
# Employee Self-Service
# ──────────────────────────────────────────────


def check_in_employee(db: Session, employee_id: int) -> Attendance:
    """Employee check-in. Creates attendance record for today if not exists."""
    from datetime import datetime
    today = date.today()

    existing = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date == today,
    ).first()

    if existing:
        if existing.check_in:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already checked in today",
            )
        existing.check_in = datetime.now()
        existing.status = AttendanceStatus.PRESENT
        db.commit()
        db.refresh(existing)
        return existing

    record = Attendance(
        employee_id=employee_id,
        date=today,
        check_in=datetime.now(),
        status=AttendanceStatus.PRESENT,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def check_out_employee(db: Session, employee_id: int) -> Attendance:
    """Employee check-out. Updates today's attendance record."""
    from datetime import datetime
    today = date.today()

    record = db.query(Attendance).filter(
        Attendance.employee_id == employee_id,
        Attendance.date == today,
    ).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No check-in found for today. Please check in first.",
        )

    if record.check_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked out today",
        )

    record.check_out = datetime.now()
    db.commit()
    db.refresh(record)
    return record


def get_my_attendance(db: Session, employee_id: int) -> list[Attendance]:
    """Get attendance records for a specific employee."""
    return db.query(Attendance).filter(
        Attendance.employee_id == employee_id
    ).order_by(Attendance.date.desc()).all()


def create_my_leave(db: Session, employee_id: int, data) -> LeaveRequest:
    """Create a leave request for the logged-in employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee record not found",
        )

    if data.start_date > data.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date",
        )

    leave = LeaveRequest(
        employee_id=employee_id,
        leave_type=data.leave_type,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


def get_my_leaves(db: Session, employee_id: int) -> list[LeaveRequest]:
    """Get leave requests for a specific employee."""
    return db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id
    ).order_by(LeaveRequest.created_at.desc()).all()


def get_dashboard_stats(db: Session) -> dict:
    today = date.today()

    total_employees = db.query(func.count(Employee.id)).filter(
        Employee.status == EmployeeStatus.ACTIVE
    ).scalar() or 0

    total_departments = db.query(func.count(Department.id)).scalar() or 0

    present_today = db.query(func.count(Attendance.id)).filter(
        Attendance.date == today,
        Attendance.status == AttendanceStatus.PRESENT,
    ).scalar() or 0

    absent_today = db.query(func.count(Attendance.id)).filter(
        Attendance.date == today,
        Attendance.status == AttendanceStatus.ABSENT,
    ).scalar() or 0

    pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
        LeaveRequest.status == LeaveStatus.PENDING
    ).scalar() or 0

    return {
        "total_employees": total_employees,
        "total_departments": total_departments,
        "present_today": present_today,
        "absent_today": absent_today,
        "pending_leaves": pending_leaves,
    }