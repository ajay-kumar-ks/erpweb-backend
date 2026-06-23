"""
AI service for CRM module using Google Gemini API.
"""
from openai import OpenAI
from app.core.config import settings
from app.modules.crm.db_models import Lead

# Try to configure Google Gemini client; fall back gracefully if unavailable
_genai_available = False
_genai_model = None
_openrouter_available = False
_openrouter_client = None

try:
    import google.generativeai as genai

    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _genai_model = genai.GenerativeModel("gemini-2.0-flash")
        _genai_available = True
    else:
        print("[ai_service] GEMINI_API_KEY is not set — Gemini AI features will use fallback")
except (ImportError, Exception) as e:
    _genai_available = False
    _genai_model = None
    print(f"[ai_service] Gemini could not be initialized — Gemini fallback enabled. Error: {e}")

try:
    if settings.OPENROUTER_API_KEY:
        _openrouter_available = True
    else:
        print("[ai_service] OPENROUTER_API_KEY is not set — OpenRouter AI features will use rule-based fallback")
except Exception as e:
    _openrouter_available = False
    print(f"[ai_service] OpenRouter configuration check failed — fallback enabled. Error: {e}")


def _normalize_openrouter_base_url(base_url: str) -> str:
    url = (base_url or "").strip()
    if url.endswith("/"):
        url = url[:-1]

    if url.startswith("https://api.openrouter.ai"):
        url = url.replace("https://api.openrouter.ai", "https://openrouter.ai/api")
    if url == "https://openrouter.ai/v1":
        url = "https://openrouter.ai/api/v1"
    return url


def _get_openrouter_client() -> OpenAI:
    global _openrouter_client
    if _openrouter_client is None:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured. Set it in your .env file.")

        base_url = _normalize_openrouter_base_url(settings.OPENROUTER_BASE_URL)
        if not base_url:
            raise ValueError("OPENROUTER_BASE_URL is not configured. Set it in your .env file.")

        print(f"[ai_service] OpenRouter base_url={base_url}")
        _openrouter_client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - CRM Assistant",
            },
        )
    return _openrouter_client


def _call_llm(prompt: str) -> str | None:
    """Call the configured LLM and return the raw text response, or None on failure."""
    global _genai_available
    if _genai_available and _genai_model:
        try:
            resp = _genai_model.generate_content(prompt)
            text = resp.text.strip() if resp else None
            print(f"[ai_service] Gemini request sent. Raw response: {text!r}")
            if text:
                return text
        except Exception as e:
            err_msg = str(e)
            print(f"[ai_service] Gemini call error ({type(e).__name__}): {err_msg}")
            if "429" in err_msg or "quota" in err_msg.lower():
                print("[ai_service] Gemini quota issue detected, disabling Gemini for subsequent requests.")
                _genai_available = False

    if _openrouter_available:
        try:
            client = _get_openrouter_client()
            normalized_base_url = _normalize_openrouter_base_url(settings.OPENROUTER_BASE_URL)
            print(f"[ai_service] Sending OpenRouter request to {normalized_base_url}")
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            text = response.choices[0].message.content.strip() if response and response.choices else None
            print(f"[ai_service] OpenRouter request sent. Raw response: {text!r}")
            return text or None
        except Exception as e:
            print(f"[ai_service] OpenRouter call error ({type(e).__name__}): {e}")
            if getattr(e, '__cause__', None):
                print(f"[ai_service] OpenRouter root cause: {type(e.__cause__).__name__}: {e.__cause__}")

    return None


def score_lead(lead: Lead) -> tuple[int, str]:
    """
    Score a lead from 0–100 using AI.
    Returns (score, reason).
    """
    if not _genai_available:
        return 50, "AI scoring not configured (set GEMINI_API_KEY)"

    # Build a compact prompt from lead data
    pipeline_id = lead.pipeline_id or "none"
    phase_id = lead.phase_id or "none"
    value = lead.value or 0
    source = lead.source or "unknown"
    title = lead.title or ""
    notes = lead.notes or ""
    extra = lead.extra_data or {}
    history = extra.get("history", [])
    days_in_pipeline = len(history)  # rough proxy

    prompt = f"""You are a lead scoring AI. Rate this lead 0-100 based on: value=${value}, source={source}, title="{title}", notes="{notes[:200]}", pipeline={pipeline_id}, phase={phase_id}, days_active={days_in_pipeline}. 
Return ONLY a JSON object: {{"score": int, "reason": "short reason"}}. No markdown."""

    text = _call_llm(prompt)
    if text is None:
        return 50, "AI scoring unavailable"

    import json
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            score = max(0, min(100, int(data.get("score", 50))))
            reason = data.get("reason", "AI evaluated")[:120]
            return score, reason
        except Exception:
            pass
    return 50, "Could not parse AI response"


def suggest_assignee(
    title: str,
    value: int | None,
    source: str | None,
    notes: str | None,
    company: str | None,
    candidates: list[dict],
) -> list[dict]:
    """
    Suggest best assignee(s) from a list of candidate employees using AI.
    Each candidate: { id, name, role, department, current_lead_count }
    Returns top 3 sorted by confidence.
    """
    if not _genai_available:
        return _suggest_assignee_fallback(candidates)

    candidate_lines = "\n".join(
        f"  - {c['name']} (ID:{c['id']}, role:{c.get('role','')}, dept:{c.get('department','')}, current leads:{c['current_lead_count']})"
        for c in candidates
    )

    prompt = f"""You are a lead assignment AI. Given this lead and a list of team members, suggest the top 3 best assignees sorted by fit.

Lead:
  Title: "{title}"
  Value: ${value or 0}
  Source: {source or 'unknown'}
  Notes: "{(notes or '')[:200]}"
  Company: "{company or 'unknown'}"

Available team members:
{candidate_lines}

Rules:
- Prioritize lower current_lead_count (workload balancing)
- Match skills/role to lead industry if inferable from title/company
- Diversity of assignment preferred

Return ONLY a JSON array of objects: [{{"employee_id": int, "confidence": int 0-100, "reason": "short reason"}}]. No markdown. No more than 3."""

    text = _call_llm(prompt)
    if text is None:
        return _suggest_assignee_fallback(candidates)

    import json
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            suggestions = json.loads(text[start:end])
            result = []
            for s in suggestions[:3]:
                emp_id = s.get("employee_id")
                candidate = next((c for c in candidates if c["id"] == emp_id), None)
                if candidate:
                    result.append({
                        "employee_id": emp_id,
                        "name": candidate["name"],
                        "confidence": max(0, min(100, int(s.get("confidence", 50)))),
                        "reason": s.get("reason", "")[:100],
                        "current_load": candidate["current_lead_count"],
                    })
            if result:
                result.sort(key=lambda x: x["confidence"], reverse=True)
                return result
        except Exception:
            pass

    return _suggest_assignee_fallback(candidates)


def _suggest_assignee_fallback(candidates: list[dict]) -> list[dict]:
    """Rule-based fallback: sort by current_lead_count ascending."""
    sorted_candidates = sorted(candidates, key=lambda c: c["current_lead_count"])
    result = []
    for c in sorted_candidates[:3]:
        result.append({
            "employee_id": c["id"],
            "name": c["name"],
            "confidence": max(0, 80 - c["current_lead_count"] * 5),
            "reason": "Lowest current workload" if c == sorted_candidates[0] else "Balanced workload distribution",
            "current_load": c["current_lead_count"],
        })
    return result


def next_best_action(lead: Lead, phases: list[dict]) -> dict:
    """
    Analyze a lead and recommend the single most impactful next action.
    Returns { action, description, suggested_phase_id, urgency }.
    """
    if not _genai_available:
        return _next_action_fallback(lead, phases)

    phase_map = {p["id"]: p["name"] for p in phases}
    phase_names = ", ".join(f'{p["name"]} (ID:{p["id"]})' for p in phases)
    current_phase_name = phase_map.get(lead.phase_id or "", "None")

    extra = lead.extra_data or {}
    history = extra.get("history", [])
    history_summary = "; ".join(
        f'{h.get("type","")}: {h.get("message","")[:60]}'
        for h in history[-5:]
    ) if history else "No history"

    prompt = f"""You are a sales acceleration AI. For this lead, recommend the single most impactful next action.

Lead:
  Title: "{lead.title or ""}"
  Value: ${lead.value or 0}
  Source: {lead.source or "unknown"}
  Current phase: {current_phase_name}
  Days in pipeline: {len(history)}
  Recent history: {history_summary}
  Notes: "{(lead.notes or "")[:200]}"

Available phases: {phase_names}

Return ONLY a JSON object:
{{
  "action": "short action name (e.g. Send follow-up email, Schedule demo, Call back, Move to X phase)",
  "description": "one-sentence justification",
  "suggested_phase_id": "phase_id or null",
  "urgency": "high|medium|low"
}}
No markdown."""

    text = _call_llm(prompt)
    if text is not None:
        import json
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                action = data.get("action", "Follow up")[:80]
                description = data.get("description", "")[:200]
                suggested_phase_id = data.get("suggested_phase_id") or None
                urgency = data.get("urgency", "medium")
                if urgency not in ("high", "medium", "low"):
                    urgency = "medium"
                return {
                    "action": action,
                    "description": description,
                    "suggested_phase_id": suggested_phase_id,
                    "urgency": urgency,
                }
            except Exception:
                pass

    return _next_action_fallback(lead, phases)


def _next_action_fallback(lead: Lead, phases: list[dict]) -> dict:
    """Rule-based fallback for next action."""
    extra = lead.extra_data or {}
    history = extra.get("history", [])
    days_in_phase = len(history)

    if days_in_phase > 10:
        next_phase = None
        for p in phases:
            if p["id"] != lead.phase_id:
                next_phase = p
                break
        return {
            "action": f"Move to {next_phase['name']}" if next_phase else "Follow up with lead",
            "description": f"Lead has been in current phase for {days_in_phase} days with no recent activity",
            "suggested_phase_id": next_phase["id"] if next_phase else None,
            "urgency": "high",
        }

    if lead.value and lead.value > 5000:
        return {
            "action": "Schedule discovery call",
            "description": f"High-value lead (${lead.value}) — prioritize personal outreach",
            "suggested_phase_id": None,
            "urgency": "high",
        }

    return {
        "action": "Send follow-up email",
        "description": "Lead is still early in the pipeline — maintain engagement",
        "suggested_phase_id": None,
        "urgency": "medium",
    }


def pipeline_insights(leads: list[Lead], phases: list[dict]) -> dict:
    """
    Analyze pipeline health using AI for rich, actionable insights.
    Returns {
        insights: [{ severity, type, message, details, count, filter_query, lead_ids, action_label }],
        summary: { score, total_value, lead_count, top_risk, top_opportunity, recommendation }
    }
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    total_value = sum(l.value or 0 for l in leads)
    total_count = len(leads)

    phase_map = {p["id"]: p["name"] for p in phases}
    lead_lines = []
    for l in leads:
        ref_date = l.updated_at or l.created_at
        days_in_phase = 0
        if ref_date:
            if ref_date.tzinfo is None:
                ref_date = ref_date.replace(tzinfo=timezone.utc)
            days_in_phase = (now - ref_date).days

        extra = l.extra_data or {}
        history = extra.get("history", [])
        recent = [h.get("message", "")[:80] for h in history[-3:]]

        lead_lines.append(
            f"- Lead: \"{l.title or 'Untitled'}\" | "
            f"Value: ${l.value or 0} | "
            f"Phase: {phase_map.get(l.phase_id, 'None')} | "
            f"Source: {l.source or 'unknown'} | "
            f"Assignee: {l.assignee or 'Unassigned'} | "
            f"Days in phase: {days_in_phase} | "
            f"Recent: {'; '.join(recent) or 'No activity'}"
        )

    pipeline_label = phases[0]["name"] if len(phases) == 1 else " - ".join(p["name"] for p in phases)
    pipeline_desc = f'{pipeline_label} ({total_count} leads, ${total_value:,} total value)'

    phase_lines = []
    for i, p in enumerate(phases):
        suffix = " (terminal)" if p.get("is_terminal") else ""
        phase_lines.append(f"  {i + 1}. {p['name']}{suffix}")
    phase_block = "\n".join(phase_lines)

    lead_block = "\n".join(lead_lines)

    prompt = (
        f'You are a senior sales pipeline analyst AI. Analyze this pipeline and return structured insights.\n\n'
        f'Pipeline: "{pipeline_desc}"\n\n'
        f'Phases in order:\n{phase_block}\n\n'
        f'Lead details:\n{lead_block}\n\n'
        'Return ONLY a valid JSON object with this exact structure. No markdown.\n\n'
        '{\n'
        '  "summary": {\n'
        '    "score": 0-100 overall pipeline health score,\n'
        f'    "total_value": {total_value},\n'
        f'    "lead_count": {total_count},\n'
        '    "top_risk": "one sentence describing the biggest risk",\n'
        '    "top_opportunity": "one sentence describing the best opportunity",\n'
        '    "recommendation": "one actionable recommendation for the team"\n'
        '  },\n'
        '  "insights": [\n'
        '    {\n'
        '      "severity": "critical|warning|info|positive",\n'
        '      "type": "risk|opportunity|bottleneck|recommendation|summary",\n'
        '      "message": "short headline (under 80 chars)",\n'
        '      "details": "detailed explanation with context (1-2 sentences)",\n'
        '      "count": number,\n'
        '      "filter_query": null or "stalled" or "phase=phase_id",\n'
        '      "lead_ids": [] or ["lead_id_1", "lead_id_2"],\n'
        '      "action_label": null or "View leads"\n'
        '    }\n'
        '  ]\n'
        '}\n\n'
        'Rules:\n'
        '- Identify stalls, bottlenecks, risks, opportunities, and patterns across leads\n'
        '- Consider value, days in phase, source, assignee workload, and activity history\n'
        '- Score 0-100: 70+ healthy, 40-69 needs attention, <40 critical\n'
        '- Maximum 6 insights total, sorted by importance\n'
        '- Use actual lead IDs from the data above for lead_ids\n'
        '- filter_query can be "stalled", "phase=phase_id", or null'
    )

    # Try AI first
    ai_result = None
    if _genai_available:
        text = _call_llm(prompt)
        if text:
            import json
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end])
                    if "insights" in data and isinstance(data["insights"], list):
                        ai_result = data
                except Exception as e:
                    print(f"[ai_service] pipeline_insights parse error: {e}")

    if ai_result:
        result = ai_result
        for ins in result.get("insights", []):
            if ins.get("lead_ids"):
                ins["lead_ids"] = [str(lid) for lid in ins["lead_ids"] if lid]
        return result

    return _pipeline_insights_fallback(leads, phases, total_value, total_count)


def _pipeline_insights_fallback(leads, phases, total_value, total_count):
    """Rule-based fallback when AI is unavailable."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    insights = []
    phase_map = {p["id"]: p for p in phases}
    leads_by_phase: dict[str, list[Lead]] = {}
    for lead in leads:
        pid = lead.phase_id or "__orphaned__"
        leads_by_phase.setdefault(pid, []).append(lead)

    # Stalled leads (>7 days in non-terminal phase)
    stalled_ids = []
    for lead in leads:
        if not lead.phase_id:
            continue
        phase = phase_map.get(lead.phase_id)
        if phase and phase.get("is_terminal"):
            continue
        ref_date = lead.updated_at or lead.created_at
        if ref_date:
            if ref_date.tzinfo is None:
                ref_date = ref_date.replace(tzinfo=timezone.utc)
            days = (now - ref_date).days
            if days > 7:
                stalled_ids.append(lead.id)

    if stalled_ids:
        insights.append({
            "severity": "critical",
            "type": "risk",
            "message": f"{len(stalled_ids)} lead(s) stalled >7 days",
            "details": "These leads have had no movement in over a week and need attention.",
            "count": len(stalled_ids),
            "filter_query": "stalled",
            "lead_ids": stalled_ids,
            "action_label": "View stalled",
        })

    # Bottleneck phase
    non_terminal_counts = [
        (pid, len(ll), phase_map.get(pid, {}).get("name", pid))
        for pid, ll in leads_by_phase.items()
        if pid != "__orphaned__" and not phase_map.get(pid, {}).get("is_terminal", False)
    ]
    if non_terminal_counts:
        non_terminal_counts.sort(key=lambda x: x[1], reverse=True)
        top_id, top_count, top_name = non_terminal_counts[0]
        if top_count >= 2:
            bottle_ids = [l.id for l in leads_by_phase.get(top_id, [])]
            insights.append({
                "severity": "warning",
                "type": "bottleneck",
                "message": f"Bottleneck in \"{top_name}\" — {top_count} lead(s) waiting",
                "details": f"Phase \"{top_name}\" has the highest concentration of leads. Consider reviewing the criteria or assigning more resources.",
                "count": top_count,
                "filter_query": f"phase={top_id}",
                "lead_ids": bottle_ids,
                "action_label": "View phase",
            })

    # Summary
    if total_value > 0:
        score = 50
        if len(stalled_ids) == 0:
            score += 20
        elif len(stalled_ids) <= total_count // 3:
            score += 10
        if total_count > 0:
            score = min(100, score)
        insights.append({
            "severity": "info",
            "type": "summary",
            "message": f"Pipeline: ${total_value:,} across {total_count} lead(s)",
            "details": f"Pipeline health score: {score}/100. {len(stalled_ids)} stalled leads need attention.",
            "count": total_count,
            "filter_query": None,
            "lead_ids": None,
            "action_label": None,
        })

    return {
        "insights": insights,
        "summary": {
            "score": 50,
            "total_value": total_value,
            "lead_count": total_count,
            "top_risk": f"{len(stalled_ids)} stalled lead(s) need attention" if stalled_ids else "No major risks detected",
            "top_opportunity": f"${total_value:,} pipeline value to advance" if total_value > 0 else "No active leads",
            "recommendation": "Review stalled leads and prioritize follow-ups." if stalled_ids else "Pipeline looks healthy — keep advancing leads through phases.",
        },
    }


def crm_chatbot(
    message: str,
    history: list[dict],
    contacts: list[dict],
    leads: list[dict],
    pipelines: list[dict],
    phases: list[dict],
    clients: list[dict],
    activities: list[dict],
    tags: list[dict],
) -> str:
    """
    CRM Chatbot: Answers user questions about CRM data only.
    Uses AI with full CRM context to answer questions.
    Falls back to a rule-based response if AI is unavailable.
    """
    if not (_genai_available or _openrouter_available):
        return _crm_chatbot_fallback(message)

    # Build a compact summary of CRM data
    contact_summary = _summarize_contacts(contacts)
    lead_summary = _summarize_leads(leads)
    pipeline_summary = _summarize_pipelines(pipelines, phases)
    client_summary = _summarize_clients(clients)
    activity_summary = _summarize_activities(activities)
    tag_summary = _summarize_tags(tags)

    # Build conversation history
    history_text = ""
    for h in history[-10:]:  # last 10 messages for context
        role = "User" if h.get("role") == "user" else "Assistant"
        content = (h.get("content", "") or "")[:500]
        history_text += f"{role}: {content}\n"

    prompt = f"""You are a helpful CRM assistant for Business Suite. You ONLY answer questions about the CRM data provided below.
If the user asks about something outside the CRM, politely say you can only assist with CRM-related questions.

Available CRM data:

=== CONTACTS ({len(contacts)} total) ===
{contact_summary}

=== LEADS ({len(leads)} total) ===
{lead_summary}

=== PIPELINES ({len(pipelines)} total) ===
{pipeline_summary}

=== CLIENTS ({len(clients)} total) ===
{client_summary}

=== ACTIVITIES ({len(activities)} recent) ===
{activity_summary}

=== TAGS ({len(tags)} total) ===
{tag_summary}

---
Previous conversation:
{history_text}

User: {message}

Respond conversationally and helpfully. Keep answers concise but informative. If the user asks for something you don't have data on, suggest what they can do in the CRM.
Assistant:"""

    text = _call_llm(prompt)
    if text:
        return text[:2000]

    # Try a deterministic data-driven fallback (counts, totals, pipeline lists)
    data_answer = _crm_chatbot_data_fallback(
        message=message,
        contacts=contacts,
        leads=leads,
        pipelines=pipelines,
        phases=phases,
        clients=clients,
        activities=activities,
        tags=tags,
    )
    if data_answer:
        print("[ai_service] Data-driven fallback answered the query.")
        return data_answer

    return _crm_chatbot_fallback(message)


def _summarize_contacts(contacts: list[dict]) -> str:
    if not contacts:
        return "No contacts in the system."
    lines = []
    for c in contacts[:20]:
        tags_str = ", ".join(t.get("name", "") for t in (c.get("tags") or [])) if c.get("tags") else ""
        lines.append(f"- {c.get('name', 'Unknown')} | Email: {c.get('email', '-')} | Phone: {c.get('phone', '-')} | Company: {c.get('company', '-')} | Tags: {tags_str or 'none'}")
    if len(contacts) > 20:
        lines.append(f"... and {len(contacts) - 20} more")
    return "\n".join(lines)


def _summarize_leads(leads: list[dict]) -> str:
    if not leads:
        return "No leads in the system."
    lines = []
    for l in leads[:20]:
        ai_score = (l.get("extra_data") or {}).get("ai_score", "N/A")
        lines.append(f"- {l.get('title', 'Untitled')} | Value: ${l.get('value', 0)} | Assignee: {l.get('assignee', 'Unassigned')} | Source: {l.get('source', 'unknown')} | AI Score: {ai_score}")
    if len(leads) > 20:
        lines.append(f"... and {len(leads) - 20} more")
    return "\n".join(lines)


def _summarize_pipelines(pipelines: list[dict], phases: list[dict]) -> str:
    if not pipelines:
        return "No pipelines configured."
    lines = []
    phase_by_pipeline = {}
    for p in phases:
        phase_by_pipeline.setdefault(p.get("pipeline_id", ""), []).append(p.get("name", ""))
    for p in pipelines[:10]:
        p_phases = phase_by_pipeline.get(p.get("id", ""), [])
        lines.append(f"- {p.get('name', 'Unnamed')} | Phases: {', '.join(p_phases) or 'none'}")
    return "\n".join(lines)


def _summarize_clients(clients: list[dict]) -> str:
    if not clients:
        return "No clients in the system."
    lines = []
    for c in clients[:15]:
        lines.append(f"- {c.get('contact_id', 'Unknown')} | Tier: {c.get('tier', 'Standard')} | Status: {c.get('status', 'Active')} | Manager: {c.get('account_manager', '-')}")
    if len(clients) > 15:
        lines.append(f"... and {len(clients) - 15} more")
    return "\n".join(lines)


def _summarize_activities(activities: list[dict]) -> str:
    if not activities:
        return "No recent activities."
    lines = []
    for a in activities[:10]:
        lines.append(f"- {a.get('title', 'Untitled')} | Type: {a.get('activity_type', '-')} | Created: {str(a.get('created_at', ''))[:10]}")
    return "\n".join(lines)


def _summarize_tags(tags: list[dict]) -> str:
    if not tags:
        return "No tags configured."
    return ", ".join(t.get("name", "") for t in tags)


def _crm_chatbot_data_fallback(
    message: str,
    contacts: list[dict],
    leads: list[dict],
    pipelines: list[dict],
    phases: list[dict],
    clients: list[dict],
    activities: list[dict],
    tags: list[dict],
) -> str | None:
    """Try to answer simple, data-driven CRM questions without AI.
    Returns a string answer when the query can be satisfied from the provided
    data, otherwise returns None to allow higher-level fallback.
    """
    q = (message or "").strip().lower()
    # Simple count queries
    if q.startswith("how many") or q.startswith("count") or "how many" in q:
        # Leads
        if "lead" in q:
            # If user asked about a pipeline by name
            for p in pipelines:
                name = (p.get("name") or "").lower()
                if name and name in q:
                    # count leads in this pipeline
                    pid = p.get("id")
                    cnt = sum(1 for l in leads if (l.get("pipeline_id") or "") == pid)
                    return f"There are {cnt} lead(s) in the '{p.get('name')}'."
            # general leads count
            return f"There are {len(leads)} lead(s) in the CRM."

        # Contacts
        if "contact" in q or "people" in q:
            return f"There are {len(contacts)} contact(s) in the CRM."

        # Clients
        if "client" in q or "customer" in q:
            return f"There are {len(clients)} client(s) in the CRM."

    # Total / sum queries
    if "total value" in q or ("value" in q and "total" in q):
        total_value = sum((l.get("value") or 0) for l in leads)
        return f"The total value across all leads is ${total_value:,}."

    # Top / high value leads
    if "high-value" in q or "high value" in q or "top leads" in q:
        sorted_leads = sorted(leads, key=lambda x: x.get("value") or 0, reverse=True)
        top = sorted_leads[:5]
        if not top:
            return "There are no leads in the CRM."
        lines = [f"- {t.get('title','Untitled')} (${t.get('value',0)})" for t in top]
        return "Top leads by value:\n" + "\n".join(lines)

    # Pipeline-specific summary
    if "pipeline" in q and ("which" in q or "list" in q or "names" in q or "what" in q):
        if not pipelines:
            return "No pipelines are configured."
        return "Pipelines:\n" + "\n".join(f"- {p.get('name')}" for p in pipelines)

    # Activities due / recent
    if "activity" in q or "activities" in q or "recent activity" in q:
        if not activities:
            return "There are no recent activities."
        recent = activities[:5]
        lines = [f"- {a.get('title','Untitled')} ({a.get('activity_type','')})" for a in recent]
        return "Recent activities:\n" + "\n".join(lines)

    return None

def _crm_chatbot_fallback(message: str) -> str:
    """Fallback response when AI is unavailable."""
    msg_lower = message.lower()

    if any(word in msg_lower for word in ["hello", "hi", "hey", "greetings"]):
        return "Hello! I'm your CRM assistant. I can help you with contacts, leads, pipelines, clients, and activities in your CRM. What would you like to know?"

    if any(word in msg_lower for word in ["contact", "person", "people"]):
        return "I can help you with contact information. You can view, create, and manage contacts in the CRM. Try asking 'How many contacts do I have?' or 'Show me contacts from a specific company.'"

    if any(word in msg_lower for word in ["lead", "pipeline", "deal", "opportunity"]):
        return "I can help with leads and pipelines. You can track leads through pipeline stages, assign team members, and score leads using AI. Try asking 'What leads are in my pipeline?' or 'Show me high-value leads.'"

    if any(word in msg_lower for word in ["client", "customer"]):
        return "I can help with client information. Clients are converted from leads. You can track client status, tier, and account managers. Try asking 'How many active clients do I have?'"

    if any(word in msg_lower for word in ["activity", "follow.up", "task"]):
        return "I can help with activities and follow-ups. Activities include calls, emails, meetings, and notes. Try asking 'What activities are due?' or 'Show me recent activity.'"

    if any(word in msg_lower for word in ["tag", "label", "category"]):
        return "Tags help organize your contacts. You can filter contacts by tags in the CRM. Try asking 'What tags do I have?' or 'Show contacts with a specific tag.'"

    return "I'm your CRM assistant. I can answer questions about your contacts, leads, pipelines, clients, activities, and tags. What would you like to know about your CRM data?"


def score_lead_basic(lead: Lead) -> tuple[int, str]:
    """
    Lightweight rule-based fallback scoring (no API call).
    Returns (score, reason).
    """
    score = 50
    factors = []

    value = lead.value or 0
    if value > 10000:
        score += 20
        factors.append("high value")
    elif value > 1000:
        score += 10
        factors.append("mid value")

    source = (lead.source or "").lower()
    if source in ("referral", "partner", "inbound"):
        score += 10
        factors.append(f"source={source}")

    if lead.assignee:
        score += 5
        factors.append("assigned")

    if lead.notes and len(lead.notes) > 20:
        score += 5
        factors.append("detailed notes")

    score = max(0, min(100, score))
    reason = ", ".join(factors) if factors else "no strong signals"
    return score, reason
