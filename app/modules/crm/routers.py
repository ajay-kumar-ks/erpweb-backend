from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from sqlalchemy.orm import joinedload
import uuid
from datetime import datetime
from typing import List, Optional

from app.core.database import get_db
from .db_models import Contact, Tag, Activity, Lead, Pipeline, Phase, Client, PipelineAssignment
from .schemas import (
    ContactCreateSchema,
    ContactUpdateSchema,
    ContactSchema,
    ContactDetailSchema,
    TagBaseSchema,
    TagSchema,
    ActivityCreateSchema,
    ActivitySchema,
    MergeContactsSchema,
    BulkActionSchema,
    LeadCreateSchema,
    LeadSchema,
    LeadUpdateSchema,
    PipelineSchema,
    PipelineCreateSchema,
    PipelineUpdateSchema,
    PhaseSchema,
    PhaseCreateSchema,
    PhaseUpdateSchema,
    ClientCreateSchema,
    ClientUpdateSchema,
    ClientSchema,
    ClientDetailSchema,
    PipelineAssignmentSchema,
    PipelineAssignmentCreateSchema,
    PipelineAssignmentUpdateSchema,
    DepartmentAssignmentConfig,
    AssignToPipelineSchema,
    AISuggestAssigneeRequest,
    AISuggestAssigneeResponse,
    AssigneeSuggestion,
    AINextActionRequest,
    AINextActionResponse,
    PipelineInsight,
    PipelineInsightsResponse,
    ChatbotRequest,
    ChatbotResponse,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])

# ============= CLIENTS ENDPOINTS (Phase 4) =============
clients_router = APIRouter(prefix="/clients", tags=["clients"])

# ============= LEADS ENDPOINTS (Phase 2) =============
leads_router = APIRouter(prefix="/leads", tags=["leads"])

# ============= PIPELINES ENDPOINTS (Phase 2) =============
pipelines_router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@pipelines_router.get("/", response_model=List[PipelineSchema])
async def list_pipelines(db: Session = Depends(get_db)):
    return db.query(Pipeline).all()


@pipelines_router.post("/", response_model=PipelineSchema, status_code=201)
async def create_pipeline(pipeline_data: PipelineCreateSchema, db: Session = Depends(get_db)):
    pipeline = Pipeline(
        id=str(uuid.uuid4()),
        name=pipeline_data.name,
        description=pipeline_data.description,
        owner=pipeline_data.owner,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


@pipelines_router.get("/{pipeline_id}", response_model=PipelineSchema)
async def get_pipeline(pipeline_id: str, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@pipelines_router.patch("/{pipeline_id}", response_model=PipelineSchema)
async def update_pipeline(pipeline_id: str, pipeline_data: PipelineUpdateSchema, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    update_data = pipeline_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pipeline, key, value)

    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline





@pipelines_router.get("/{pipeline_id}/phases", response_model=List[PhaseSchema])
async def list_pipeline_phases(pipeline_id: str, db: Session = Depends(get_db)):
    return db.query(Phase).filter(Phase.pipeline_id == pipeline_id).order_by(Phase.position).all()


@pipelines_router.post("/{pipeline_id}/phases", response_model=PhaseSchema, status_code=201)
async def create_pipeline_phase(pipeline_id: str, phase_data: PhaseCreateSchema, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    phase_position = phase_data.position
    if phase_position is None:
        highest_position = db.query(Phase.position).filter(Phase.pipeline_id == pipeline_id).order_by(Phase.position.desc()).first()
        phase_position = highest_position[0] + 1 if highest_position and highest_position[0] is not None else 0

    phase = Phase(
        id=str(uuid.uuid4()),
        pipeline_id=pipeline_id,
        name=phase_data.name,
        color=phase_data.color or "#6b7280",
        position=phase_position,
        is_terminal=phase_data.is_terminal or False,
    )
    db.add(phase)
    db.commit()
    db.refresh(phase)
    return phase


@pipelines_router.put("/{pipeline_id}/phases/{phase_id}", response_model=PhaseSchema)
async def update_pipeline_phase(
    pipeline_id: str,
    phase_id: str,
    phase_data: PhaseUpdateSchema,
    db: Session = Depends(get_db),
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    phase = db.query(Phase).filter(Phase.id == phase_id, Phase.pipeline_id == pipeline_id).first()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    update_data = phase_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(phase, key, value)

    db.add(phase)
    db.commit()
    db.refresh(phase)
    return phase





@pipelines_router.delete("/{pipeline_id}/phases/{phase_id}", status_code=204)
async def delete_pipeline_phase(pipeline_id: str, phase_id: str, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    phase = db.query(Phase).filter(Phase.id == phase_id, Phase.pipeline_id == pipeline_id).first()
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    # Remove phase references from leads before deleting the phase
    db.query(Lead).filter(Lead.phase_id == phase_id).update({Lead.phase_id: None}, synchronize_session=False)
    db.delete(phase)
    db.commit()


# ════════════════════════════════════════════════════════════
# PIPELINE ASSIGNMENT ENDPOINTS
# ════════════════════════════════════════════════════════════


@pipelines_router.get("/{pipeline_id}/assignments", response_model=PipelineAssignmentSchema)
async def get_pipeline_assignment(pipeline_id: str, db: Session = Depends(get_db)):
    """Get pipeline assignment configuration."""
    assignment = db.query(PipelineAssignment).filter(PipelineAssignment.pipeline_id == pipeline_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment config found for this pipeline")
    return assignment


@pipelines_router.put("/{pipeline_id}/assignments", response_model=PipelineAssignmentSchema)
async def save_pipeline_assignment(
    pipeline_id: str,
    data: PipelineAssignmentUpdateSchema,
    db: Session = Depends(get_db),
):
    """Create or update pipeline assignment configuration.
    Stores department-level assignment rules for the pipeline.
    """
    # Verify pipeline exists
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    assignment = db.query(PipelineAssignment).filter(PipelineAssignment.pipeline_id == pipeline_id).first()

    if assignment:
        assignment.departments_config = [
            dept.model_dump() for dept in data.departments_config
        ]
        assignment.updated_at = datetime.utcnow()
    else:
        assignment = PipelineAssignment(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            departments_config=[
                dept.model_dump() for dept in data.departments_config
            ],
        )
        db.add(assignment)

    db.commit()
    db.refresh(assignment)
    return assignment


@pipelines_router.post("/{pipeline_id}/assignments/apply")
async def apply_pipeline_assignment(
    pipeline_id: str,
    data: AssignToPipelineSchema,
    db: Session = Depends(get_db),
):
    """Apply assignment rules to existing leads in the pipeline.
    - round_robin: Distribute unassigned leads among selected members
    - individual: Assign all leads to the designated member
    """
    assignment = db.query(PipelineAssignment).filter(PipelineAssignment.pipeline_id == pipeline_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment config found for this pipeline")

    # Find the department config
    dept_config = None
    for dc in assignment.departments_config:
        if dc.get("department_id") == data.department_id:
            dept_config = dc
            break

    if not dept_config:
        raise HTTPException(status_code=404, detail=f"Department {data.department_id} not found in assignment config")

    leads_to_update = db.query(Lead).filter(
        Lead.pipeline_id == pipeline_id
    ).all()

    updated_count = 0

    if data.assignment_mode == "self_assign":
        # Self-assign mode doesn't bulk-assign leads — it's handled at lead creation time
        raise HTTPException(status_code=400, detail="Self-assign mode does not support bulk assignment. Use Save to configure for new leads.")

    if data.assignment_mode == "round_robin":
        selected_members = dept_config.get("selected_members", [])
        if not selected_members:
            raise HTTPException(status_code=400, detail="No members selected for round robin")

        # Fetch employee names for selected member IDs
        from app.modules.hr.crud import get_employee
        members = []
        for emp_id in selected_members:
            emp = get_employee(db, emp_id)
            if emp:
                members.append(emp.user.full_name or emp.user.username or str(emp.id))

        if not members:
            raise HTTPException(status_code=400, detail="No valid members found for round robin")

        # Assign round-robin to all existing leads in the pipeline
        idx = dept_config.get("round_robin_index", 0)
        for lead in leads_to_update:
            lead.assignee = members[idx % len(members)]
            idx += 1
            updated_count += 1

        # Update the round_robin_index in the stored config
        for dc in assignment.departments_config:
            if dc.get("department_id") == data.department_id:
                dc["round_robin_index"] = idx % len(members)
                break
        assignment.departments_config = assignment.departments_config

    elif data.assignment_mode == "individual":
        assignee_id = dept_config.get("individual_assignee_id")
        if not assignee_id:
            raise HTTPException(status_code=400, detail="No individual assignee selected")

        from app.modules.hr.crud import get_employee
        emp = get_employee(db, assignee_id)
        if not emp:
            raise HTTPException(status_code=404, detail="Assignee employee not found")
        assignee_name = emp.user.full_name or emp.user.username or str(emp.id)

        for lead in leads_to_update:
            lead.assignee = assignee_name
            updated_count += 1

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported assignment mode: {data.assignment_mode}")

    db.commit()

    return {
        "success": True,
        "pipeline_id": pipeline_id,
        "department_id": data.department_id,
        "assignment_mode": data.assignment_mode,
        "updated_count": updated_count,
    }


@leads_router.post("/", response_model=LeadSchema, status_code=201)
async def create_lead(lead_data: LeadCreateSchema, db: Session = Depends(get_db)):
    lead_id = str(uuid.uuid4())
    lead_extra_data = lead_data.extra_data or {}
    lead_extra_data.setdefault('history', [])
    lead_extra_data['history'].append({
        'type': 'created',
        'message': 'Lead created',
        'timestamp': datetime.utcnow().isoformat(),
    })

    lead = Lead(
        id=lead_id,
        title=lead_data.title,
        contact_id=lead_data.contact_id,
        pipeline_id=lead_data.pipeline_id,
        phase_id=lead_data.phase_id,
        value=lead_data.value,
        expected_close_date=lead_data.expected_close_date,
        assignee=lead_data.assignee,
        source=lead_data.source,
        notes=lead_data.notes,
        extra_data=lead_extra_data
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@leads_router.get("/", response_model=List[LeadSchema])
async def list_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    pipeline_id: Optional[str] = Query(None),
    phase_id: Optional[str] = Query(None),
    assignee: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    orphaned: Optional[bool] = Query(None, description="Filter leads with pipeline_id set but phase_id null"),
    db: Session = Depends(get_db)
):
    query = db.query(Lead).options(joinedload(Lead.contact), joinedload(Lead.pipeline), joinedload(Lead.phase))

    if pipeline_id:
        query = query.filter(Lead.pipeline_id == pipeline_id)
    if phase_id:
        query = query.filter(Lead.phase_id == phase_id)
    if assignee:
        query = query.filter(Lead.assignee.ilike(f"%{assignee}%"))
    if source:
        query = query.filter(Lead.source.ilike(f"%{source}%"))
    if search:
        search_term = f"%{search}%"
        query = query.filter(Lead.title.ilike(search_term))
    if orphaned:
        query = query.filter(Lead.pipeline_id.isnot(None), Lead.phase_id.is_(None))

    leads = query.offset(skip).limit(limit).all()
    return leads


@leads_router.get("/{lead_id}", response_model=LeadSchema)
async def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@leads_router.put("/{lead_id}", response_model=LeadSchema)
async def update_lead(lead_id: str, lead_data: LeadUpdateSchema, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    update_data = lead_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lead, key, value)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@leads_router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()


@leads_router.put("/{lead_id}/move")
async def move_lead(lead_id: str, phase_id: str = Query(...), db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Check if destination phase creates clients
    destination_phase = db.query(Phase).filter(Phase.id == phase_id).first()
    if not destination_phase:
        raise HTTPException(status_code=404, detail="Phase not found")

    old_phase_id = lead.phase_id
    lead.phase_id = phase_id
    extra_data = lead.extra_data or {}
    history = extra_data.get('history', [])
    history.append({
        'type': 'phase_changed',
        'message': f"Moved from {old_phase_id or 'None'} to {phase_id}",
        'from_phase_id': old_phase_id,
        'to_phase_id': phase_id,
        'timestamp': datetime.utcnow().isoformat(),
    })
    extra_data['history'] = history
    extra_data['converted'] = destination_phase.creates_client
    lead.extra_data = extra_data

    db.add(lead)
    db.flush()

    # Auto-create client if destination phase is a client-conversion phase
    created_client_id = None
    if destination_phase.creates_client and lead.contact_id:
        # Check if client already exists
        existing_client = db.query(Client).filter(Client.lead_id == lead.id).first()
        if not existing_client:
            client = Client(
                id=str(uuid.uuid4()),
                contact_id=lead.contact_id,
                lead_id=lead.id,
                tier="Standard",
                status="Active",
                account_manager=lead.assignee,
            )
            db.add(client)
            db.flush()
            created_client_id = client.id

    db.commit()
    db.refresh(lead)
    
    response = {"success": True, "lead_id": lead.id, "phase_id": phase_id}
    if created_client_id:
        response["client_created"] = True
        response["client_id"] = created_client_id
    
    return response


@leads_router.post("/{lead_id}/convert")
async def convert_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Update lead history
    extra_data = lead.extra_data or {}
    history = extra_data.get('history', [])
    history.append({
        'type': 'converted',
        'message': 'Lead converted to Client',
        'timestamp': datetime.utcnow().isoformat(),
    })
    extra_data['history'] = history
    extra_data['converted'] = True
    lead.extra_data = extra_data

    # Create Client record from Lead
    client = Client(
        id=str(uuid.uuid4()),
        contact_id=lead.contact_id,
        lead_id=lead.id,
        tier="Standard",
        status="Active",
    )
    
    db.add(lead)
    db.add(client)
    db.commit()
    db.refresh(lead)
    db.refresh(client)
    
    # TODO: publish event_bus message for crm.lead.converted
    return {"success": True, "lead_id": lead.id, "client_id": client.id}


# ════════════════════════════════════════════════════════════
# AI ENDPOINTS (Phase 1 — Lead Scoring)
# ════════════════════════════════════════════════════════════


@leads_router.post("/{lead_id}/score")
async def score_lead_ai(lead_id: str, db: Session = Depends(get_db)):
    """Score a single lead using Gemini AI. Stores result in extra_data."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.modules.crm.ai_service import score_lead as ai_score
    from sqlalchemy.orm.attributes import flag_modified
    score, reason = ai_score(lead)

    extra = dict(lead.extra_data or {})
    extra["ai_score"] = score
    extra["ai_score_reason"] = reason
    extra["ai_scored_at"] = datetime.utcnow().isoformat()
    lead.extra_data = extra
    flag_modified(lead, "extra_data")

    db.add(lead)
    db.commit()
    db.refresh(lead)

    return {"lead_id": lead.id, "score": score, "reason": reason}


@leads_router.post("/score-all")
async def score_all_leads_ai(pipeline_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Score all leads (optionally filtered by pipeline)."""
    query = db.query(Lead)
    if pipeline_id:
        query = query.filter(Lead.pipeline_id == pipeline_id)

    leads = query.all()
    from app.modules.crm.ai_service import score_lead_basic
    from sqlalchemy.orm.attributes import flag_modified
    results = []
    for lead in leads:
        score, reason = score_lead_basic(lead)
        extra = dict(lead.extra_data or {})
        extra["ai_score"] = score
        extra["ai_score_reason"] = reason
        extra["ai_scored_at"] = datetime.utcnow().isoformat()
        lead.extra_data = extra
        flag_modified(lead, "extra_data")
        db.add(lead)
        results.append({"lead_id": lead.id, "score": score, "reason": reason})

    db.commit()
    return {"scored": len(results), "results": results}


# ════════════════════════════════════════════════════════════
# AI ENDPOINTS (Phase 2 — Smart Lead Assignment)
# ════════════════════════════════════════════════════════════

ai_router = APIRouter(prefix="/ai", tags=["ai"])


@ai_router.post("/suggest-assignee", response_model=AISuggestAssigneeResponse)
async def suggest_assignee_ai(
    data: AISuggestAssigneeRequest,
    db: Session = Depends(get_db),
):
    """
    Given lead details + pipeline_id, return top 3 suggested assignees
    based on workload, role fit, and past performance.
    """
    # 1. Find pipeline assignment config
    assignment = db.query(PipelineAssignment).filter(
        PipelineAssignment.pipeline_id == data.pipeline_id
    ).first()
    if not assignment or not assignment.departments_config:
        raise HTTPException(
            status_code=404,
            detail="No assignment config found for this pipeline. Configure department groups in Settings > Assign Member first."
        )

    # 2. Collect employee IDs from all configured departments
    from app.modules.hr.crud import get_employee

    candidate_emp_ids = set()
    for dc in assignment.departments_config:
        members = dc.get("selected_members", [])
        if dc.get("individual_assignee_id"):
            members.append(dc["individual_assignee_id"])
        for eid in members:
            candidate_emp_ids.add(eid)

    if not candidate_emp_ids:
        raise HTTPException(
            status_code=400,
            detail="No members configured in pipeline assignment. Add members in Settings > Assign Member first."
        )

    # 3. Build candidate list with workload counts
    candidates = []
    for eid in candidate_emp_ids:
        emp = get_employee(db, eid)
        if not emp:
            continue
        # Count current leads assigned to this employee in this pipeline
        lead_count = db.query(Lead).filter(
            Lead.assignee == (emp.user.full_name or emp.user.username or str(emp.id)),
            Lead.pipeline_id == data.pipeline_id,
        ).count()

        candidates.append({
            "id": emp.id,
            "name": emp.user.full_name or emp.user.username or f"Employee #{emp.id}",
            "role": emp.role.name if emp.role else "",
            "department": emp.department.name if emp.department else "",
            "current_lead_count": lead_count,
        })

    if not candidates:
        raise HTTPException(status_code=400, detail="No valid employees found from pipeline assignment config")

    # 4. Call AI service for suggestions
    from app.modules.crm.ai_service import suggest_assignee as ai_suggest
    suggestions = ai_suggest(
        title=data.title,
        value=data.value,
        source=data.source,
        notes=data.notes,
        company=data.contact_company,
        candidates=candidates,
    )

    return AISuggestAssigneeResponse(suggestions=suggestions)


@ai_router.post("/next-action", response_model=AINextActionResponse)
async def next_best_action_ai(
    data: AINextActionRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze a lead and recommend the single most impactful next action.
    Based on current phase, days in phase, value, history, notes, and source.
    Returns action, description, suggested_phase_id, and urgency.
    """
    lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Get all phases for this lead's pipeline
    phases_q = db.query(Phase).filter(Phase.pipeline_id == lead.pipeline_id).order_by(Phase.position).all()
    phases = [{"id": p.id, "name": p.name} for p in phases_q]

    from app.modules.crm.ai_service import next_best_action as ai_next
    result = ai_next(lead, phases)

    return AINextActionResponse(**result)


@ai_router.post("/chat")
async def crm_chatbot(
    data: ChatbotRequest,
    db: Session = Depends(get_db),
):
    """
    CRM Chatbot: Answers user questions about CRM data.
    Uses Gemini AI with full CRM context to provide intelligent responses.
    Only answers questions related to CRM content.
    """
    # Fetch all CRM data
    contacts = db.query(Contact).all()
    leads = db.query(Lead).all()
    pipelines = db.query(Pipeline).all()
    phases = db.query(Phase).all()
    clients = db.query(Client).all()
    recent_activities = db.query(Activity).order_by(Activity.created_at.desc()).limit(25).all()
    tags = db.query(Tag).all()

    # Convert to dicts for the AI service
    from app.modules.crm.ai_service import crm_chatbot as ai_chat

    contacts_data = []
    for c in contacts:
        d = {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "company": c.company,
            "job_title": c.job_title,
            "status": c.status,
            "source": c.source,
            "tags": [{"name": t.name, "color": t.color} for t in (c.tags or [])],
            "notes": c.notes,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        contacts_data.append(d)

    leads_data = []
    for l in leads:
        d = {
            "id": l.id,
            "title": l.title,
            "value": l.value,
            "assignee": l.assignee,
            "source": l.source,
            "notes": l.notes,
            "extra_data": l.extra_data,
            "phase_id": l.phase_id,
            "pipeline_id": l.pipeline_id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "updated_at": l.updated_at.isoformat() if l.updated_at else None,
        }
        leads_data.append(d)

    pipelines_data = []
    for p in pipelines:
        d = {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "owner": p.owner,
        }
        pipelines_data.append(d)

    phases_data = []
    for p in phases:
        d = {
            "id": p.id,
            "pipeline_id": p.pipeline_id,
            "name": p.name,
            "position": p.position,
            "is_terminal": p.is_terminal,
        }
        phases_data.append(d)

    clients_data = []
    for c in clients:
        d = {
            "id": c.id,
            "contact_id": c.contact_id,
            "lead_id": c.lead_id,
            "tier": c.tier,
            "status": c.status,
            "account_manager": c.account_manager,
            "client_since": c.client_since.isoformat() if c.client_since else None,
        }
        clients_data.append(d)

    activities_data = []
    for a in recent_activities:
        d = {
            "id": a.id,
            "contact_id": a.contact_id,
            "activity_type": a.activity_type,
            "title": a.title,
            "description": a.description,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        activities_data.append(d)

    tags_data = [{"name": t.name, "color": t.color} for t in tags]

    history = [{"role": m.role, "content": m.content} for m in data.history]

    reply = ai_chat(
        message=data.message,
        history=history,
        contacts=contacts_data,
        leads=leads_data,
        pipelines=pipelines_data,
        phases=phases_data,
        clients=clients_data,
        activities=activities_data,
        tags=tags_data,
    )

    return ChatbotResponse(reply=reply)


@ai_router.post("/pipeline-insights", response_model=PipelineInsightsResponse)
async def pipeline_insights_ai(
    pipeline_id: str,
    db: Session = Depends(get_db),
):
    """
    Analyze a pipeline using AI and return structured health insights.
    Uses Gemini AI to identify risks, opportunities, bottlenecks, and recommendations.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    # Get all leads in this pipeline
    leads = db.query(Lead).filter(Lead.pipeline_id == pipeline_id).all()

    # Get all phases for this pipeline
    phases_q = db.query(Phase).filter(Phase.pipeline_id == pipeline_id).order_by(Phase.position).all()
    phases = [{
        "id": p.id,
        "name": p.name,
        "position": p.position,
        "is_terminal": p.is_terminal,
    } for p in phases_q]

    from app.modules.crm.ai_service import pipeline_insights as ai_insights
    result = ai_insights(leads, phases)

    return PipelineInsightsResponse(
        insights=result.get("insights", []),
        summary=result.get("summary"),
        pipeline_id=pipeline_id,
        pipeline_name=pipeline.name,
    )


# ════════════════════════════════════════════════════════════
# CLIENTS ENDPOINTS (Phase 4) ✅ 4.1 ✅ 4.2
# ════════════════════════════════════════════════════════════


@clients_router.post("/", response_model=ClientSchema, status_code=201)
async def create_client(client_data: ClientCreateSchema, db: Session = Depends(get_db)):
    """Create a new client (from lead or directly)"""
    # Validate contact exists
    contact = db.query(Contact).filter(Contact.id == client_data.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Check if client already exists for this contact
    existing_client = db.query(Client).filter(Client.contact_id == client_data.contact_id).first()
    if existing_client:
        raise HTTPException(status_code=400, detail="Client already exists for this contact")
    
    client = Client(
        id=str(uuid.uuid4()),
        contact_id=client_data.contact_id,
        lead_id=client_data.lead_id,
        account_manager=client_data.account_manager,
        tier=client_data.tier or "Standard",
    )
    
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@clients_router.get("/", response_model=List[ClientSchema])
async def list_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    tier: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    account_manager: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """List clients with filtering"""
    query = db.query(Client)
    
    if tier:
        query = query.filter(Client.tier == tier)
    if status:
        query = query.filter(Client.status == status)
    if account_manager:
        query = query.filter(Client.account_manager.ilike(f"%{account_manager}%"))
    if search:
        # Search in linked contact name
        search_term = f"%{search}%"
        query = query.join(Contact).filter(Contact.name.ilike(search_term))
    
    clients = query.offset(skip).limit(limit).all()
    return clients


@clients_router.get("/{client_id}", response_model=ClientDetailSchema)
async def get_client(client_id: str, db: Session = Depends(get_db)):
    """Get client details with contact info"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@clients_router.put("/{client_id}", response_model=ClientSchema)
async def update_client(client_id: str, client_data: ClientUpdateSchema, db: Session = Depends(get_db)):
    """Update client information"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@clients_router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: str, db: Session = Depends(get_db)):
    """Delete a client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()


@clients_router.post("/{client_id}/add-project")
async def add_project_to_client(client_id: str, project_data: dict, db: Session = Depends(get_db)):
    """Link a project/deal to client"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    linked_projects = client.linked_projects or []
    linked_projects.append({
        "project_id": project_data.get("project_id"),
        "project_name": project_data.get("project_name"),
        "module": project_data.get("module"),  # tasks, accounts, etc
        "added_at": datetime.utcnow().isoformat()
    })
    client.linked_projects = linked_projects
    
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"success": True, "client_id": client.id}


# ============= CONTACTS ENDPOINTS =============

@router.post("/", response_model=ContactSchema, status_code=201)
async def create_contact(contact_data: ContactCreateSchema, db: Session = Depends(get_db)):
    """Create a new contact with validation"""
    
    # Validate at least email or phone is provided
    if not contact_data.email and not contact_data.phone:
        raise HTTPException(
            status_code=400,
            detail="At least one of email or phone is required"
        )
    
    # Create contact instance
    contact_id = str(uuid.uuid4())
    contact = Contact(
        id=contact_id,
        name=contact_data.name,
        email=contact_data.email,
        phone=contact_data.phone,
        company=contact_data.company,
        job_title=contact_data.job_title,
        address=contact_data.address,
        notes=contact_data.notes,
        avatar_url=contact_data.avatar_url,
        custom_fields=[
            field.dict() if hasattr(field, 'dict') else field
            for field in contact_data.custom_fields
        ] if contact_data.custom_fields else [],
        source=contact_data.source,
    )
    
    # Link tags
    if contact_data.tags:
        for tag_name in contact_data.tags:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(id=str(uuid.uuid4()), name=tag_name)
                db.add(tag)
            contact.tags.append(tag)
    
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/", response_model=List[ContactSchema])
async def list_contacts(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    tags: Optional[str] = Query(None),  # comma-separated
    status: Optional[str] = "all",
    db: Session = Depends(get_db)
):
    """List contacts with search, filter, and pagination"""
    
    query = db.query(Contact)
    
    # Filter by status unless the client requests all statuses
    if status and status.lower() != "all":
        query = query.filter(Contact.status == status)
    
    # Search by name, email, phone, company
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(search_term),
                Contact.email.ilike(search_term),
                Contact.phone.ilike(search_term),
                Contact.company.ilike(search_term),
            )
        )
    
    # Filter by tags
    if tags:
        tag_names = [t.strip() for t in tags.split(",")]
        query = query.filter(Contact.tags.any(Tag.name.in_(tag_names)))
    
    total = query.count()
    response.headers["X-Total-Count"] = str(total)
    contacts = query.offset(skip).limit(limit).all()
    return contacts


@router.get("/{contact_id}", response_model=ContactDetailSchema)
async def get_contact(contact_id: str, db: Session = Depends(get_db)):
    """Get contact details with activity timeline"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return contact


@router.put("/{contact_id}", response_model=ContactSchema)
async def update_contact(
    contact_id: str,
    contact_data: ContactUpdateSchema,
    db: Session = Depends(get_db)
):
    """Update contact information"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Update fields
    update_data = contact_data.dict(exclude_unset=True)

    # Handle custom fields
    if "custom_fields" in update_data:
        custom_fields_data = update_data.pop("custom_fields")
        contact.custom_fields = [
            field if isinstance(field, dict) else field.dict()
            for field in custom_fields_data
        ]
    
    # Handle tags
    if "tags" in update_data:
        tag_names = update_data.pop("tags")
        contact.tags.clear()
        for tag_name in tag_names:
            tag = db.query(Tag).filter(Tag.name == tag_name).first()
            if not tag:
                tag = Tag(id=str(uuid.uuid4()), name=tag_name)
                db.add(tag)
            contact.tags.append(tag)
    
    for key, value in update_data.items():
        setattr(contact, key, value)

    if update_data.get('status') == 'active':
        contact.deleted_at = None
        contact.archived_at = None
    elif update_data.get('status') == 'archived':
        contact.archived_at = datetime.utcnow()
        contact.deleted_at = None
    elif update_data.get('status') == 'deleted':
        contact.deleted_at = datetime.utcnow()

    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, db: Session = Depends(get_db)):
    """Soft-delete a contact by flagging it as deleted"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.status = "deleted"
    contact.deleted_at = datetime.utcnow()
    db.commit()


@router.patch("/{contact_id}/archive", response_model=ContactSchema)
async def archive_contact(contact_id: str, db: Session = Depends(get_db)):
    """Archive a contact instead of deleting"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact.status = "archived"
    contact.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(contact)
    return contact


@router.post("/{contact_id}/merge", response_model=ContactSchema)
async def merge_contacts(
    contact_id: str,
    merge_data: MergeContactsSchema,
    db: Session = Depends(get_db)
):
    """
    Merge two contacts - combine data, keep primary
    """
    primary = db.query(Contact).filter(Contact.id == merge_data.primary_id).first()
    secondary = db.query(Contact).filter(Contact.id == merge_data.secondary_id).first()
    
    if not primary or not secondary:
        raise HTTPException(status_code=404, detail="One or both contacts not found")
    
    if primary.id == secondary.id:
        raise HTTPException(status_code=400, detail="Cannot merge contact with itself")
    
    # Merge tags
    for tag in secondary.tags:
        if tag not in primary.tags:
            primary.tags.append(tag)
    
    # Merge custom fields
    primary_fields = {f["label"]: f for f in primary.custom_fields}
    for field in secondary.custom_fields:
        if field["label"] not in primary_fields:
            primary.custom_fields.append(field)
    
    # Merge activities
    for activity in secondary.activities:
        activity.contact_id = primary.id
    
    # Delete secondary
    db.delete(secondary)
    db.commit()
    db.refresh(primary)
    return primary


@router.post("/bulk-action")
async def bulk_action(action_data: BulkActionSchema, db: Session = Depends(get_db)):
    """Perform bulk actions on multiple contacts"""
    
    contacts = db.query(Contact).filter(Contact.id.in_(action_data.contact_ids)).all()
    
    if action_data.action == "tag":
        tag_name = action_data.action_data.get("tag_name")
        if not tag_name:
            raise HTTPException(status_code=400, detail="tag_name required")
        
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(id=str(uuid.uuid4()), name=tag_name)
            db.add(tag)
        
        for contact in contacts:
            if tag not in contact.tags:
                contact.tags.append(tag)
    
    elif action_data.action == "archive":
        for contact in contacts:
            contact.status = "archived"
            contact.archived_at = datetime.utcnow()
    
    db.commit()
    return {"success": True, "count": len(contacts)}


# ============= ACTIVITIES ENDPOINTS =============

@router.post("/{contact_id}/activities", response_model=ActivitySchema, status_code=201)
async def add_activity(
    contact_id: str,
    activity_data: ActivityCreateSchema,
    db: Session = Depends(get_db)
):
    """Add activity to contact (call, email, meeting, note)"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    activity = Activity(
        id=str(uuid.uuid4()),
        contact_id=contact_id,
        activity_type=activity_data.activity_type,
        title=activity_data.title,
        description=activity_data.description,
        follow_up_date=activity_data.follow_up_date,
        meta_data=activity_data.meta_data or {},
    )
    
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


@router.get("/{contact_id}/activities", response_model=List[ActivitySchema])
async def get_activities(contact_id: str, db: Session = Depends(get_db)):
    """Get activity timeline for contact"""
    
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    activities = db.query(Activity).filter(Activity.contact_id == contact_id).order_by(Activity.created_at.desc()).all()
    return activities


@router.get("/activities", response_model=List[ActivitySchema])
async def list_activities(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """List recent activities across contacts"""
    query = db.query(Activity).order_by(Activity.created_at.desc())
    activities = query.offset(skip).limit(limit).all()
    return activities


@router.get("/notifications/followups")
async def get_due_followups(limit: int = 10, db: Session = Depends(get_db)):
    """Return due follow-up activities (follow_up_date <= now)."""
    now = datetime.utcnow()
    base_q = db.query(Activity).filter(Activity.follow_up_date != None, Activity.follow_up_date <= now)
    total = base_q.count()
    items = base_q.order_by(Activity.follow_up_date.asc()).limit(limit).all()

    results = []
    for a in items:
        results.append({
            "id": a.id,
            "contact_id": a.contact_id,
            "title": a.title,
            "follow_up_date": a.follow_up_date.isoformat() if a.follow_up_date else None,
            "activity_type": a.activity_type,
        })

    return {"count": total, "items": results}


# ============= TAGS ENDPOINTS =============

@router.get("/tags", response_model=List[TagSchema])
async def list_tags(db: Session = Depends(get_db)):
    """List all available tags"""
    tags = db.query(Tag).all()
    return tags


@router.post("/tags", response_model=TagSchema, status_code=201)
async def create_tag(tag_data: TagBaseSchema, db: Session = Depends(get_db)):
    """Create a new tag"""
    
    existing = db.query(Tag).filter(Tag.name == tag_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    
    tag = Tag(
        id=str(uuid.uuid4()),
        name=tag_data.name,
        color=tag_data.color or "#6366f1"
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


# Health check
@router.get("/health")
async def health():
    return {"status": "CRM module ready"}

