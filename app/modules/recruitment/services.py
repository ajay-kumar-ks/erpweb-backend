from app.modules.recruitment.db_models import Candidate


def format_candidate_response(candidate: Candidate) -> dict:
    role_name = None
    if candidate.role:
        role_name = candidate.role.name

    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "position_applied": candidate.position_applied,
        "role_id": candidate.role_id,
        "role_name": role_name,
        "experience_years": candidate.experience_years,
        "current_stage": candidate.current_stage,
        "pipeline_stages": candidate.pipeline_stages,
        "status": candidate.status,
        "converted_to_employee": candidate.converted_to_employee,
        "resume_url": candidate.resume_url,
        "notes": candidate.notes,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }
