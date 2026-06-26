from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from app.core.database import get_db
from app.modules.auth.routers import get_current_user
from app.modules.auth.models import User
from app.modules.hr.crud import (
    get_employees,
    get_employee,
    create_employee,
    update_employee,
    delete_employee,
    get_departments,
    get_department,
    create_department,
    update_department,
    delete_department,
    get_attendance,
    mark_attendance,
    get_attendance_by_employee,
    get_leave_requests,
    create_leave_request,
    update_leave_status,
    get_dashboard_stats,
    get_hr_users,
    create_hr_user,
    update_hr_user,
    delete_hr_user,
    get_employee_by_user_id,
    check_in_employee,
    check_out_employee,
    get_my_attendance,
    create_my_leave,
    get_my_leaves,
)
from app.modules.hr.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    AttendanceCreate,
    AttendanceResponse,
    AttendanceListResponse,
    LeaveCreate,
    LeaveStatusUpdate,
    LeaveResponse,
    UserCreate,
    UserUpdate,
    UserResponse,
    MyLeaveCreate,
    ChatbotRequest,
    ChatbotResponse,
    JobDescriptionRequest,
    JobDescriptionResponse,
)
from app.modules.hr.services import format_employee_response, format_attendance_response, format_leave_response
from app.modules.hr.db_models import (
    EmployeeStatus, AttendanceStatus, LeaveType, LeaveStatus,
    Employee, Department, Attendance, LeaveRequest,
)
from app.modules.auth.db_models import User as UserDB
from app.modules.recruitment.db_models import Candidate
from sqlalchemy import func

router = APIRouter()


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def require_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# ──────────────────────────────────────────────
# Health check (existing)
# ──────────────────────────────────────────────


@router.get("/")
async def health():
    return {"status": "HR module ready"}


# ──────────────────────────────────────────────
# Employee Self-Service
# ──────────────────────────────────────────────


@router.get("/me")
async def api_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        return {
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "is_admin": current_user.is_admin,
            },
            "employee": None,
        }

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_admin": current_user.is_admin,
        },
        "employee": format_employee_response(employee),
    }


@router.get("/me/attendance")
async def api_my_attendance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile found")

    records = get_my_attendance(db, employee.id)
    return [format_attendance_response(r) for r in records]


@router.post("/me/attendance/checkin")
async def api_check_in(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile found")

    record = check_in_employee(db, employee.id)
    return format_attendance_response(record)


@router.post("/me/attendance/checkout")
async def api_check_out(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile found")

    record = check_out_employee(db, employee.id)
    return format_attendance_response(record)


@router.get("/me/leaves")
async def api_my_leaves(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile found")

    leaves = get_my_leaves(db, employee.id)
    return [format_leave_response(l) for l in leaves]


@router.post("/me/leaves", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def api_create_my_leave(
    data: MyLeaveCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    employee = get_employee_by_user_id(db, current_user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="No employee profile found")

    leave = create_my_leave(db, employee.id, data)
    return format_leave_response(leave)


# ──────────────────────────────────────────────
# HR User Management (Admin only)
# ──────────────────────────────────────────────


@router.get("/users", response_model=list[UserResponse])
async def api_get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return get_hr_users(db)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def api_create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_hr_user(db, data)


@router.put("/users/{user_id}", response_model=UserResponse)
async def api_update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Prevent self-demotion: a user cannot change their own is_admin flag
    if user_id == current_user.id and data.is_admin is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot change your own admin privileges. Ask another admin to modify this.",
        )

    user = update_hr_user(db, user_id, data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = delete_hr_user(db, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )


# ──────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────


@router.get("/dashboard")
async def api_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return get_dashboard_stats(db)


# ──────────────────────────────────────────────
# Employee CRUD
# ──────────────────────────────────────────────


@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def api_create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    employee = create_employee(db, data)
    return format_employee_response(employee)


@router.get("/employees", response_model=EmployeeListResponse)
async def api_get_employees(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[EmployeeStatus] = None,
    search: Optional[str] = None,
    department_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    employees, total = get_employees(
        db, skip=skip, limit=limit, status_filter=status, search=search, department_id=department_id
    )
    return {
        "employees": [format_employee_response(e) for e in employees],
        "total": total,
    }


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
async def api_get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    employee = get_employee(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found",
        )
    return format_employee_response(employee)


@router.put("/employees/{employee_id}", response_model=EmployeeResponse)
async def api_update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    employee = update_employee(db, employee_id, data)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found",
        )
    return format_employee_response(employee)


@router.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = delete_employee(db, employee_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found",
        )


# ──────────────────────────────────────────────
# Department CRUD
# ──────────────────────────────────────────────


@router.get("/departments", response_model=list[DepartmentResponse])
async def api_get_departments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return get_departments(db)


@router.post("/departments", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def api_create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_department(db, data)


@router.put("/departments/{department_id}", response_model=DepartmentResponse)
async def api_update_department(
    department_id: int,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    department = update_department(db, department_id, data)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )
    return department


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = delete_department(db, department_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )


# ──────────────────────────────────────────────
# Attendance CRUD
# ──────────────────────────────────────────────


@router.post("/attendance", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
async def api_mark_attendance(
    data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    record = mark_attendance(db, data)
    return format_attendance_response(record)


@router.get("/attendance", response_model=AttendanceListResponse)
async def api_get_attendance(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    employee_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    records, total = get_attendance(
        db, skip=skip, limit=limit, employee_id=employee_id,
        date_from=date_from, date_to=date_to
    )
    return {
        "attendance_records": [format_attendance_response(r) for r in records],
        "total": total,
    }


@router.get("/attendance/{employee_id}", response_model=list[AttendanceResponse])
async def api_get_employee_attendance(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return [format_attendance_response(r) for r in get_attendance_by_employee(db, employee_id)]


# ──────────────────────────────────────────────
# Leave CRUD
# ──────────────────────────────────────────────


@router.post("/leaves", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def api_create_leave(
    data: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leave = create_leave_request(db, data)
    return format_leave_response(leave)


@router.get("/leaves", response_model=list[LeaveResponse])
async def api_get_leaves(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leaves, total = get_leave_requests(db, skip=skip, limit=limit)
    return [format_leave_response(l) for l in leaves]


@router.patch("/leaves/{leave_id}", response_model=LeaveResponse)
async def api_update_leave_status(
    leave_id: int,
    data: LeaveStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    leave = update_leave_status(db, leave_id, data)
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with id {leave_id} not found",
        )
    return format_leave_response(leave)


# ──────────────────────────────────────────────
# AI Job Description Generator
# ──────────────────────────────────────────────


@router.post("/ai/job-description", response_model=JobDescriptionResponse)
async def api_generate_job_description(
    data: JobDescriptionRequest,
    current_user: User = Depends(require_admin),
):
    """Generate a professional ATS-friendly job description using AI."""
    try:
        from app.services.hr_ai_service import generate_job_description

        jd_text = generate_job_description(data.model_dump())
        return JobDescriptionResponse(
            success=True,
            job_description=jd_text,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service configuration error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate job description: {str(e)[:200]}",
        )


# ──────────────────────────────────────────────
# AI Insights
# ──────────────────────────────────────────────


@router.get("/ai-insights")
async def api_hr_ai_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Generate AI-powered HR insights from real HR data."""
    try:
        from app.services.hr_ai_service import generate_hr_insights

        # ── Collect Workforce Data ──
        total_employees = db.query(func.count(Employee.id)).scalar() or 0
        total_departments = db.query(func.count(Department.id)).scalar() or 0
        active_employees = db.query(func.count(Employee.id)).filter(
            Employee.status == EmployeeStatus.ACTIVE
        ).scalar() or 0
        inactive_employees = db.query(func.count(Employee.id)).filter(
            Employee.status == EmployeeStatus.INACTIVE
        ).scalar() or 0

        # Employees per department
        dept_query = db.query(
            Department.name, func.count(Employee.id)
        ).outerjoin(
            Employee, Employee.department_id == Department.id
        ).group_by(Department.name).all()
        employees_per_department = {name: count for name, count in dept_query}

        # ── Collect Recruitment Data ──
        total_candidates = db.query(func.count(Candidate.id)).scalar() or 0
        candidates_in_progress = db.query(func.count(Candidate.id)).filter(
            Candidate.status == "In Progress"
        ).scalar() or 0
        selected_candidates = db.query(func.count(Candidate.id)).filter(
            Candidate.current_stage == "Selected"
        ).scalar() or 0
        onboarded_candidates = db.query(func.count(Candidate.id)).filter(
            Candidate.current_stage == "Onboarded"
        ).scalar() or 0
        converted_employees = db.query(func.count(Candidate.id)).filter(
            Candidate.converted_to_employee == True
        ).scalar() or 0
        rejected_candidates = db.query(func.count(Candidate.id)).filter(
            Candidate.current_stage == "Rejected"
        ).scalar() or 0

        # ── Collect Attendance Data ──
        total_attendance_records = db.query(func.count(Attendance.id)).scalar() or 0
        present_employees = db.query(func.count(Attendance.id)).filter(
            Attendance.status == AttendanceStatus.PRESENT
        ).scalar() or 0
        absent_employees = db.query(func.count(Attendance.id)).filter(
            Attendance.status == AttendanceStatus.ABSENT
        ).scalar() or 0
        attendance_percentage = (
            (present_employees / total_attendance_records * 100)
            if total_attendance_records > 0 else 0
        )

        # ── Collect Leave Data ──
        total_leave_requests = db.query(func.count(LeaveRequest.id)).scalar() or 0
        approved_leaves = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == LeaveStatus.APPROVED
        ).scalar() or 0
        pending_leaves = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == LeaveStatus.PENDING
        ).scalar() or 0
        rejected_leaves = db.query(func.count(LeaveRequest.id)).filter(
            LeaveRequest.status == LeaveStatus.REJECTED
        ).scalar() or 0

        # ── Build HR data dict ──
        hr_data = {
            "total_employees": total_employees,
            "total_departments": total_departments,
            "active_employees": active_employees,
            "inactive_employees": inactive_employees,
            "employees_per_department": employees_per_department,
            "total_candidates": total_candidates,
            "candidates_in_progress": candidates_in_progress,
            "selected_candidates": selected_candidates,
            "onboarded_candidates": onboarded_candidates,
            "converted_employees": converted_employees,
            "rejected_candidates": rejected_candidates,
            "total_attendance_records": total_attendance_records,
            "present_employees": present_employees,
            "absent_employees": absent_employees,
            "attendance_percentage": round(attendance_percentage, 1),
            "total_leave_requests": total_leave_requests,
            "approved_leaves": approved_leaves,
            "pending_leaves": pending_leaves,
            "rejected_leaves": rejected_leaves,
        }

        # ── Generate AI insights ──
        insights = generate_hr_insights(hr_data)
        return {
            "success": True,
            "data": hr_data,
            "insights": insights,
        }

    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service module not available. Check your backend installation.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service configuration error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI insights: {str(e)[:200]}",
        )


# ──────────────────────────────────────────────
# HR Chatbot (conversational AI)
# ──────────────────────────────────────────────


@router.post("/ai/chat")
async def api_hr_chatbot(
    data: ChatbotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    HR Chatbot: Answers user questions about HR data.
    Uses AI with full HR context to provide intelligent responses.
    Only answers questions related to HR content.
    """
    # Fetch all HR data
    employees = db.query(Employee).all()
    departments = db.query(Department).all()
    attendance_records = db.query(Attendance).order_by(Attendance.date.desc()).limit(100).all()
    leaves = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc()).limit(100).all()
    candidates = db.query(Candidate).all()
    users = db.query(UserDB).all()

    # Convert to dicts for the AI service
    from app.modules.hr.services import format_employee_response, format_attendance_response, format_leave_response

    employees_data = []
    for emp in employees:
        d = format_employee_response(emp)
        employees_data.append(d)

    departments_data = []
    for dept in departments:
        d = {
            "id": dept.id,
            "name": dept.name,
            "description": dept.description,
        }
        departments_data.append(d)

    attendance_data = [format_attendance_response(r) for r in attendance_records]

    leaves_data = [format_leave_response(l) for l in leaves]

    candidates_data = []
    for c in candidates:
        d = {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "department_name": c.department.name if c.department else None,
            "current_stage": c.current_stage,
            "status": c.status,
            "experience_years": c.experience_years,
        }
        candidates_data.append(d)

    users_data = []
    for u in users:
        d = {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "is_admin": u.is_admin,
        }
        users_data.append(d)

    from app.modules.hr.hr_chatbot_service import hr_chatbot as ai_chat

    history = [{"role": m.role, "content": m.content} for m in data.history]

    reply = ai_chat(
        message=data.message,
        history=history,
        employees=employees_data,
        departments=departments_data,
        attendance_records=attendance_data,
        leaves=leaves_data,
        candidates=candidates_data,
        users=users_data,
    )

    return ChatbotResponse(reply=reply)
