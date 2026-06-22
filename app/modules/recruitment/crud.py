from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from app.modules.recruitment.db_models import (
    Candidate,
    PipelineTemplate,
    can_move_to_stage,
    DEFAULT_PIPELINES,
)
from app.modules.recruitment.schemas import CandidateCreate, CandidateUpdate
from app.modules.hr.db_models import Role, Employee, EmployeeStatus
from app.modules.hr.crud import generate_employee_code, get_role


# ──────────────────────────────────────────────
# Pipeline Template CRUD
# ──────────────────────────────────────────────


def get_pipeline_templates(db: Session) -> list[PipelineTemplate]:
    return db.query(PipelineTemplate).order_by(PipelineTemplate.id).all()


def get_pipeline_template(db: Session, template_id: int) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.id == template_id).first()


def get_pipeline_template_by_role(db: Session, role_id: int) -> PipelineTemplate | None:
    return db.query(PipelineTemplate).filter(PipelineTemplate.role_id == role_id).first()


def create_pipeline_template(db: Session, data) -> PipelineTemplate:
    existing = get_pipeline_template_by_role(db, data.role_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline template already exists for role_id {data.role_id}",
        )

    # Validate role exists
    role = get_role(db, data.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id {data.role_id} not found",
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
        role_id=data.role_id,
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


def get_default_stages_for_role(role_name: str) -> list[str]:
    """Get default pipeline stages based on role name hint."""
    # Check exact match first
    if role_name in DEFAULT_PIPELINES:
        return list(DEFAULT_PIPELINES[role_name])
    # Check partial match
    for key, stages in DEFAULT_PIPELINES.items():
        if key.lower() in role_name.lower() or role_name.lower() in key.lower():
            return list(stages)
    return list(DEFAULT_PIPELINES["default"])


def seed_default_pipeline_templates(db: Session):
    """Auto-create pipeline templates for roles that don't have one yet."""
    roles = db.query(Role).all()
    created = 0
    for role in roles:
        existing = get_pipeline_template_by_role(db, role.id)
        if existing:
            continue
        stages = get_default_stages_for_role(role.name)
        template = PipelineTemplate(
            role_id=role.id,
            stages=stages,
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

    # Determine position and pipeline
    position = data.position_applied
    pipeline_stages = None

    if data.role_id:
        role = get_role(db, data.role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role with id {data.role_id} not found",
            )
        if not position:
            position = role.name

        # Get pipeline template for this role
        template = get_pipeline_template_by_role(db, data.role_id)
        if template:
            pipeline_stages = list(template.stages)

    # If no role or no template, use default pipeline
    if not pipeline_stages:
        pipeline_stages = list(DEFAULT_PIPELINES["default"])

    candidate = Candidate(
        full_name=data.full_name,
        email=data.email,
        phone=data.phone,
        position_applied=position or "Unknown",
        role_id=data.role_id,
        experience_years=data.experience_years,
        notes=data.notes,
        resume_url=data.resume_url,
        current_stage=pipeline_stages[0] if pipeline_stages else "Applied",
        pipeline_stages=pipeline_stages,
        status="active",
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

    # If role_id changed, update pipeline stages
    if "role_id" in update_data and update_data["role_id"] != candidate.role_id:
        if update_data["role_id"]:
            template = get_pipeline_template_by_role(db, update_data["role_id"])
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


# ──────────────────────────────────────────────
# Convert to Employee (from Onboarded stage only)
# ──────────────────────────────────────────────


def convert_candidate_to_employee(
    db: Session,
    candidate_id: int,
    data,
) -> dict:
    """
    Convert an Onboarded candidate into an Employee record.
    Does NOT create a User account — that's a separate process.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )

    if candidate.current_stage != "Onboarded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate is in '{candidate.current_stage}' stage. Only 'Onboarded' candidates can be converted.",
        )

    if candidate.converted_to_employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Candidate has already been converted to an employee",
        )

    # Create employee record (no user account)
    employee_code = data.employee_code or generate_employee_code(db)

    employee = Employee(
        user_id=None,  # No user account — will be assigned later
        employee_code=employee_code,
        phone=data.phone or candidate.phone,
        department_id=data.department_id,
        role_id=data.role_id or candidate.role_id,
        joining_date=data.joining_date,
        salary=data.salary,
        status=EmployeeStatus.ACTIVE,
    )
    db.add(employee)

    # Mark candidate as converted
    candidate.converted_to_employee = True
    candidate.status = "converted"

    db.commit()
    db.refresh(employee)
    db.refresh(candidate)

    return {
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": candidate.full_name,
            "email": candidate.email,
            "status": employee.status.value if employee.status else None,
        },
        "candidate": {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "current_stage": candidate.current_stage,
            "converted_to_employee": candidate.converted_to_employee,
            "status": candidate.status,
        },
        "message": (
            f"Candidate '{candidate.full_name}' converted to employee (Code: {employee_code}). "
            f"A user account can be created separately in User Management."
        ),
    }


# ──────────────────────────────────────────────
# Dashboard / Reports
# ──────────────────────────────────────────────


def get_recruitment_stats(db: Session) -> dict:
    total = db.query(func.count(Candidate.id)).scalar() or 0

    in_progress = db.query(func.count(Candidate.id)).filter(
        Candidate.status == "active"
    ).scalar() or 0

    # Selected = candidates in 'Selected' stage (or the stage before Onboarded)
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


def get_candidates_by_position(db: Session) -> list[dict]:
    rows = (
        db.query(
            Candidate.position_applied,
            func.count(Candidate.id).label("count"),
        )
        .group_by(Candidate.position_applied)
        .order_by(func.count(Candidate.id).desc())
        .all()
    )
    return [{"position": row.position_applied, "count": row.count} for row in rows]


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
