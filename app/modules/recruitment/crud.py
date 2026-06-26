from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.modules.recruitment.db_models import (
    Candidate,
    PipelineTemplate,
    can_move_to_stage,
    DEFAULT_PIPELINE_STAGES,
)
from app.modules.recruitment.schemas import CandidateCreate, CandidateUpdate
from app.modules.hr.db_models import Employee, EmployeeStatus
from app.modules.hr.crud import generate_employee_code
from app.modules.auth.db_models import User
from app.modules.auth.utils import get_password_hash
from datetime import date


# ──────────────────────────────────────────────
# Pipeline Template CRUD
# ──────────────────────────────────────────────


def get_pipeline_templates(db: Session) -> list[PipelineTemplate]:
    return db.query(PipelineTemplate).order_by(PipelineTemplate.id).all()


def get_pipeline_template(db: Session, template_id: int) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()


def get_pipeline_template_by_department(db: Session, department_id: int) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.department_id == department_id).first()


def create_pipeline_template(db: Session, data) -> PipelineTemplate:
    existing = get_pipeline_template_by_department(db, data.department_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline template already exists for department_id {data.department_id}",
        )

    # Validate stages — must have at least 2 stages, end with Onboarded, start with Applied
    if len(data.stages) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pipeline must have at least 2 stages",
        )
    if data.stages[0] != "Applied":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="First stage must be 'Applied'",
        )
    if data.stages[-1] != "Onboarded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Last stage must be 'Onboarded'",
        )

    template = PipelineTemplate(
        department_id=data.department_id,
        stages=data.stages,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_pipeline_template(db: Session, template_id: int, data) -> PipelineTemplate | None:
    template = get_pipeline_template(db, template_id)
    if not template:
        return None

    if data.stages is not None:
        if len(data.stages) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline must have at least 2 stages",
            )
        if data.stages[0] != "Applied":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="First stage must be 'Applied'",
            )
        if data.stages[-1] != "Onboarded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Last stage must be 'Onboarded'",
            )
        template.stages = data.stages

    db.commit()
    db.refresh(template)
    return template


def delete_pipeline_template(db: Session, template_id: int) -> bool:
    template = get_pipeline_template(db, template_id)
    if not template:
        return False
    db.delete(template)
    db.commit()
    return True


def seed_default_pipeline_templates(db: Session):
    """Auto-create pipeline templates for departments that don't have one yet."""
    from app.modules.hr.db_models import Department
    departments = db.query(Department).all()
    created = 0
    for dept in departments:
        existing = get_pipeline_template_by_department(db, dept.id)
        if existing:
            continue
        template = PipelineTemplate(
            department_id=dept.id,
            stages=list(DEFAULT_PIPELINE_STAGES),
        )
        db.add(template)
        created += 1
    if created > 0:
        db.commit()
    return created


# ──────────────────────────────────────────────
# Candidate CRUD
# ──────────────────────────────────────────────


def get_candidates(db: Session, skip: int = 0, limit: int = 100) -> list[Candidate]:
    return db.query(Candidate).order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()


def get_candidate(db: Session, candidate_id: int) -> Candidate | None:
    return db.query(Candidate).filter(Candidate.id == candidate_id).first()


def create_candidate(db: Session, data: CandidateCreate) -> Candidate:
    existing = db.query(Candidate).filter(Candidate.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate with email '{data.email}' already exists",
        )

    # Department is required; validate that it has a pipeline template
    if not data.department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department is required to create a candidate.",
        )

    template = get_pipeline_template_by_department(db, data.department_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please configure a pipeline template for this department before adding candidates.",
        )

    pipeline_stages = list(template.stages)

    candidate = Candidate(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        department_id=data.department_id,
        experience_years=data.experience_years,
        notes=data.notes,
        resume_url=data.resume_url,
        current_stage=pipeline_stages[0],
        pipeline_stages=pipeline_stages,
        status="In Progress",
        converted_to_employee=False,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


def update_candidate(db: Session, candidate_id: int, data: CandidateUpdate) -> Candidate | None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Check email uniqueness if changed
    if "email" in update_data and update_data["email"] != candidate.email:
        existing = db.query(Candidate).filter(Candidate.email == update_data["email"]).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Candidate with email '{update_data['email']}' already exists",
            )

    # If department_id changed, update pipeline stages
    if "department_id" in update_data and update_data["department_id"] != candidate.department_id:
        if update_data["department_id"]:
            template = get_pipeline_template_by_department(db, update_data["department_id"])
            if template:
                update_data["pipeline_stages"] = list(template.stages)

    for key, value in update_data.items():
        setattr(candidate, key, value)

    db.commit()
    db.refresh(candidate)
    return candidate


def delete_candidate(db: Session, candidate_id: int) -> bool:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return False
    db.delete(candidate)
    db.commit()
    return True


# ──────────────────────────────────────────────
# Stage Management
# ──────────────────────────────────────────────


def move_candidate_stage(db: Session, candidate_id: int, target_stage: str) -> Candidate | None:
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None

    # Validate the move using dynamic pipeline
    if not can_move_to_stage(candidate, target_stage):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot move from '{candidate.current_stage}' to '{target_stage}'. "
                f"Allowed transitions: forward progression or Rejected."
            ),
        )

    candidate.current_stage = target_stage

    # Update status based on stage
    if target_stage == "Rejected":
        candidate.status = "rejected"
    elif target_stage == "Onboarded":
        candidate.status = "onboarded"

    db.commit()
    db.refresh(candidate)

    return candidate



def convert_candidate_to_employee(db: Session, candidate_id: int, username: str, password: str) -> Candidate | None:
    """
    Manually convert an Onboarded candidate to an Employee.
    Creates a User (login account) with the provided username/password.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        return None

    if candidate.current_stage != "Onboarded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate must be in 'Onboarded' stage to convert to employee.",
        )

    if candidate.converted_to_employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has already been converted to an employee.",
        )

    # Validate username uniqueness
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already taken. Please choose a different username.",
        )

    # 1. Create User account with provided credentials
    user = User(
        username=username,
        email=candidate.email or "",
        full_name=candidate.full_name,
        hashed_password=get_password_hash(password),
        disabled=False,
        is_admin=False,
    )
    db.add(user)
    db.flush()  # Get user.id before creating employee

    # 2. Create Employee linked to user
    employee_code = generate_employee_code(db)
    employee = Employee(
        user_id=user.id,
        employee_code=employee_code,
        full_name=candidate.full_name,
        email=candidate.email,
        phone=candidate.phone,
        department_id=candidate.department_id,
        joining_date=date.today(),
        salary=None,
        status=EmployeeStatus.ACTIVE,
    )
    db.add(employee)

    # 3. Mark candidate as converted
    candidate.converted_to_employee = True
    candidate.status = "converted"

    db.commit()
    db.refresh(employee)
    db.refresh(candidate)

    return candidate


# ──────────────────────────────────────────────
# Dashboard / Reports
# ──────────────────────────────────────────────


def get_recruitment_stats(db: Session) -> dict:
    total = db.query(func.count(Candidate.id)).scalar() or 0

    in_progress = db.query(func.count(Candidate.id)).filter(
        Candidate.status == "In Progress"
    ).scalar() or 0

    # Selected = candidates in 'Selected' stage
    selected = db.query(func.count(Candidate.id)).filter(
        Candidate.current_stage == "Selected"
    ).scalar() or 0

    onboarded = db.query(func.count(Candidate.id)).filter(
        Candidate.current_stage == "Onboarded"
    ).scalar() or 0

    converted = db.query(func.count(Candidate.id)).filter(
        Candidate.converted_to_employee == True
    ).scalar() or 0

    rejected = db.query(func.count(Candidate.id)).filter(
        Candidate.status == "rejected"
    ).scalar() or 0

    return {
        "total_candidates": total,
        "in_progress": in_progress,
        "selected": selected,
        "onboarded": onboarded,
        "converted": converted,
        "rejected": rejected,
    }


def get_candidates_by_department(db: Session) -> list[dict]:
    from app.modules.hr.db_models import Department
    rows = (
        db.query(
            Department.name,
            func.count(Candidate.id).label("count"),
        )
        .join(Candidate, Candidate.department_id == Department.id, isouter=True)
        .group_by(Department.name)
        .order_by(func.count(Candidate.id).desc())
        .all()
    )
    return [{"department": row.name, "count": row.count} for row in rows]


def get_candidates_by_stage(db: Session) -> list[dict]:
    rows = (
        db.query(
            Candidate.current_stage,
            func.count(Candidate.id).label("count"),
        )
        .group_by(Candidate.current_stage)
        .order_by(Candidate.current_stage)
        .all()
    )
    return [{"stage": row.current_stage, "count": row.count} for row in rows]


def get_hiring_stats(db: Session) -> dict:
    total = db.query(func.count(Candidate.id)).scalar() or 1
    converted = db.query(func.count(Candidate.id)).filter(
        Candidate.converted_to_employee == True
    ).scalar() or 0
    rejected = db.query(func.count(Candidate.id)).filter(
        Candidate.status == "rejected"
    ).scalar() or 0

    success_rate = round((converted / total) * 100, 1) if total > 0 else 0

    return {
        "total_candidates": total,
        "converted": converted,
        "rejected": rejected,
        "success_rate": success_rate,
    }
