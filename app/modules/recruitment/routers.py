from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.modules.auth.routers import get_current_user
from app.modules.auth.models import User
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse,
    MoveStageRequest,
    ConvertToEmployeeRequest,
    PipelineTemplateCreate,
    PipelineTemplateUpdate,
    PipelineTemplateResponse,
)
from app.modules.recruitment.crud import (
    get_candidates,
    get_candidate,
    create_candidate,
    update_candidate,
    delete_candidate,
    move_candidate_stage,
    convert_candidate_to_employee,
    get_recruitment_stats,
    get_candidates_by_department,
    get_candidates_by_stage,
    get_hiring_stats,
    get_pipeline_templates,
    get_pipeline_template,
    create_pipeline_template,
    update_pipeline_template,
    delete_pipeline_template,
    seed_default_pipeline_templates,
)
from app.modules.recruitment.services import format_candidate_response

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
# Health
# ──────────────────────────────────────────────


@router.get("/")
async def health():
    return {"status": "Recruitment module ready"}


# ──────────────────────────────────────────────
# Pipeline Templates
# ──────────────────────────────────────────────


@router.get("/pipeline-templates", response_model=list[PipelineTemplateResponse])
async def api_get_pipeline_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    templates = get_pipeline_templates(db)
    result = []
    for t in templates:
        result.append({
            "id": t.id,
            "department_id": t.department_id,
            "stages": t.stages,
            "department_name": t.department.name if t.department else None,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        })
    return result


@router.get("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def api_get_pipeline_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = get_pipeline_template(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline template with id {template_id} not found",
        )
    return {
        "id": template.id,
        "department_id": template.department_id,
        "stages": template.stages,
        "department_name": template.department.name if template.department else None,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.post("/pipeline-templates", response_model=PipelineTemplateResponse, status_code=status.HTTP_201_CREATED)
async def api_create_pipeline_template(
    data: PipelineTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = create_pipeline_template(db, data)
    return {
        "id": template.id,
        "department_id": template.department_id,
        "stages": template.stages,
        "department_name": template.department.name if template.department else None,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.put("/pipeline-templates/{template_id}", response_model=PipelineTemplateResponse)
async def api_update_pipeline_template(
    template_id: int,
    data: PipelineTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = update_pipeline_template(db, template_id, data)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline template with id {template_id} not found",
        )
    return {
        "id": template.id,
        "department_id": template.department_id,
        "stages": template.stages,
        "department_name": template.department.name if template.department else None,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.delete("/pipeline-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_pipeline_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = delete_pipeline_template(db, template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline template with id {template_id} not found",
        )


@router.post("/seed-pipelines")
async def api_seed_pipeline_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Auto-create pipeline templates for departments that don't have one yet."""
    created = seed_default_pipeline_templates(db)
    return {"message": f"Created {created} pipeline template(s)", "created": created}


# ──────────────────────────────────────────────
# Candidate CRUD
# ──────────────────────────────────────────────


@router.get("/candidates", response_model=list[CandidateResponse])
async def api_get_candidates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return [format_candidate_response(c) for c in get_candidates(db, skip=skip, limit=limit)]


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
async def api_get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    candidate = get_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )
    return format_candidate_response(candidate)


@router.post("/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def api_create_candidate(
    data: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    candidate = create_candidate(db, data)
    return format_candidate_response(candidate)


@router.put("/candidates/{candidate_id}", response_model=CandidateResponse)
async def api_update_candidate(
    candidate_id: int,
    data: CandidateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    candidate = update_candidate(db, candidate_id, data)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )
    return format_candidate_response(candidate)


@router.delete("/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def api_delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = delete_candidate(db, candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )


# ──────────────────────────────────────────────
# Stage Management
# ──────────────────────────────────────────────


@router.post("/candidates/{candidate_id}/move-stage", response_model=CandidateResponse)
async def api_move_candidate_stage(
    candidate_id: int,
    data: MoveStageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    candidate = move_candidate_stage(db, candidate_id, data.target_stage)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )
    return format_candidate_response(candidate)


# ──────────────────────────────────────────────
# Employee Conversion
# ──────────────────────────────────────────────


@router.post("/candidates/{candidate_id}/convert")
async def api_convert_candidate_to_employee(
    candidate_id: int,
    data: ConvertToEmployeeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Convert an Onboarded candidate to an Employee record and create a login account."""
    candidate = convert_candidate_to_employee(db, candidate_id, data.username, data.password)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate with id {candidate_id} not found",
        )
    return {
        "candidate": format_candidate_response(candidate),
        "credentials": {
            "username": data.username,
            "email": candidate.email,
        },
    }


# ──────────────────────────────────────────────
# Dashboard & Reports
# ──────────────────────────────────────────────


@router.get("/dashboard")
async def api_recruitment_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    stats = get_recruitment_stats(db)
    by_department = get_candidates_by_department(db)
    by_stage = get_candidates_by_stage(db)
    hiring = get_hiring_stats(db)
    return {
        **stats,
        "by_department": by_department,
        "by_stage": by_stage,
        "hiring": hiring,
    }
