"""
AI-powered HR Insights service.

Connects to OpenRouter (OpenAI-compatible API) to generate
intelligent HR analytics and recommendations based on
workforce, recruitment, attendance, and leave data.
"""

import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Client initialisation (lazy)
# ──────────────────────────────────────────────

_insights_client = None
_jd_client = None

_insights_client = None
_jd_client = None


def _get_insights_client():
    """Lazy-init the OpenAI client for HR insights using API_KEY2."""
    global _insights_client
    if _insights_client is None:
        from openai import OpenAI
        api_key = settings.OPENROUTER_API_KEY2
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY2 is not configured. "
                "Set it in your .env file."
            )
        _insights_client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - HR AI Insights",
            },
        )
    return _insights_client


def _get_jd_client():
    """Lazy-init the OpenAI client for Job Description generation using API_KEY2."""
    global _jd_client
    if _jd_client is None:
        from openai import OpenAI
        api_key = settings.OPENROUTER_API_KEY2
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY2 is not configured. "
                "Set it in your .env file."
            )
        _jd_client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - AI Job Description Generator",
            },
        )
    return _jd_client


# ══════════════════════════════════════════════
# HR INSIGHTS (Existing)
# ══════════════════════════════════════════════

# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert Human Resources Analytics Consultant.

Analyze the provided HR data and generate:

1. Executive Summary
2. Workforce Insights
3. Recruitment Insights
4. Attendance Insights
5. Leave Management Insights
6. Risks or Concerns
7. Actionable Recommendations

Keep responses concise, professional, and business-oriented.

Respond ONLY with valid JSON — no markdown, no explanations. The JSON object must have exactly these keys:
{
  "executive_summary": "string",
  "workforce_insights": ["string", ...],
  "recruitment_insights": ["string", ...],
  "attendance_insights": ["string", ...],
  "leave_insights": ["string", ...],
  "risks": ["string", ...],
  "recommendations": ["string", ...]
}
"""


# ──────────────────────────────────────────────
# Prompt builder
# ──────────────────────────────────────────────


def build_hr_context(data: dict) -> str:
    """Build a structured HR data summary for the AI prompt."""
    lines = ["HR Data Summary", "=" * 40, ""]

    # Workforce
    lines.append("WORKFORCE DATA")
    lines.append(f"  Total Employees: {data.get('total_employees', 0)}")
    lines.append(f"  Total Departments: {data.get('total_departments', 0)}")
    lines.append(f"  Active Employees: {data.get('active_employees', 0)}")
    lines.append(f"  Inactive Employees: {data.get('inactive_employees', 0)}")
    employees_per_dept = data.get('employees_per_department', {})
    if employees_per_dept:
        lines.append("  Employees per Department:")
        for dept, count in employees_per_dept.items():
            lines.append(f"    - {dept}: {count}")
    lines.append("")

    # Recruitment
    lines.append("RECRUITMENT DATA")
    lines.append(f"  Total Candidates: {data.get('total_candidates', 0)}")
    lines.append(f"  Candidates In Progress: {data.get('candidates_in_progress', 0)}")
    lines.append(f"  Selected Candidates: {data.get('selected_candidates', 0)}")
    lines.append(f"  Onboarded Candidates: {data.get('onboarded_candidates', 0)}")
    lines.append(f"  Converted Employees: {data.get('converted_employees', 0)}")
    lines.append(f"  Rejected Candidates: {data.get('rejected_candidates', 0)}")
    lines.append("")

    # Attendance
    lines.append("ATTENDANCE DATA")
    lines.append(f"  Total Attendance Records: {data.get('total_attendance_records', 0)}")
    lines.append(f"  Present Employees: {data.get('present_employees', 0)}")
    lines.append(f"  Absent Employees: {data.get('absent_employees', 0)}")
    lines.append(f"  Attendance Percentage: {data.get('attendance_percentage', 0):.1f}%")
    lines.append("")

    # Leave
    lines.append("LEAVE DATA")
    lines.append(f"  Total Leave Requests: {data.get('total_leave_requests', 0)}")
    lines.append(f"  Approved Leaves: {data.get('approved_leaves', 0)}")
    lines.append(f"  Pending Leaves: {data.get('pending_leaves', 0)}")
    lines.append(f"  Rejected Leaves: {data.get('rejected_leaves', 0)}")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Response parser
# ──────────────────────────────────────────────


def parse_ai_response(raw: str) -> dict:
    """Try to extract a JSON object from the AI response."""
    text = raw.strip()
    if text.startswith("```"):
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse AI response as JSON:\n%s", raw)
        return {
            "executive_summary": "Could not generate insights at this time.",
            "workforce_insights": [],
            "recruitment_insights": [],
            "attendance_insights": [],
            "leave_insights": [],
            "risks": [],
            "recommendations": [],
        }


# ──────────────────────────────────────────────
# Main insight function
# ──────────────────────────────────────────────


def generate_hr_insights(hr_data: dict) -> dict:
    """Generate AI-powered HR insights based on provided HR data.

    Args:
        hr_data: Dictionary with HR statistics including workforce,
                 recruitment, attendance, and leave data.

    Returns:
        Dictionary with keys: executive_summary, workforce_insights,
        recruitment_insights, attendance_insights, leave_insights,
        risks, recommendations.
    """
    try:
        client = _get_insights_client()
        context = build_hr_context(hr_data)

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this HR data and provide insights:\n\n{context}"},
            ],
            temperature=0.3,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content or ""
        result = parse_ai_response(raw)

        # Validate and normalise fields
        for key in ["workforce_insights", "recruitment_insights", "attendance_insights", "leave_insights", "risks", "recommendations"]:
            if not isinstance(result.get(key), list):
                result[key] = []
        if not isinstance(result.get("executive_summary"), str):
            result["executive_summary"] = "Analysis complete."

        return result

    except ValueError as e:
        logger.error("HR AI service configuration error: %s", e)
        return {
            "executive_summary": f"Configuration error: {e}",
            "workforce_insights": [],
            "recruitment_insights": [],
            "attendance_insights": [],
            "leave_insights": [],
            "risks": [],
            "recommendations": [],
        }
    except Exception as e:
        logger.exception("HR AI insight request failed")
        return {
            "executive_summary": f"Sorry, I couldn't generate insights right now. Error: {str(e)[:100]}",
            "workforce_insights": [],
            "recruitment_insights": [],
            "attendance_insights": [],
            "leave_insights": [],
            "risks": [],
            "recommendations": [],
        }


# ══════════════════════════════════════════════
# AI JOB DESCRIPTION GENERATOR
# ══════════════════════════════════════════════

JD_SYSTEM_PROMPT = """\
You are an expert HR professional specializing in creating ATS-friendly job descriptions.

Generate a professional, comprehensive job description based on the provided inputs.

Requirements:
* Professional HR language
* ATS-friendly formatting
* Clear bullet points
* No company-specific information
* Do NOT invent salary, location, employment type, benefits or company details
* Return clean formatted text only — no JSON, no markdown code blocks.
"""


def build_jd_prompt(data: dict) -> str:
    """Build the prompt for job description generation."""
    dept = data.get("department", "")
    title = data.get("job_title", "")
    exp = data.get("experience", "")
    skills = data.get("skills", "")
    extra = data.get("additional_requirements", "")

    prompt = f"""Generate a professional ATS-friendly job description.

Inputs:

Department: {dept}

Job Title: {title}

Experience Required: {exp}

Required Skills:
{skills}

Additional Requirements:
{extra}

Generate the following sections:

1. Job Summary

2. Key Responsibilities

3. Required Skills

4. Qualifications

5. Preferred Skills

Requirements:

* Professional HR language
* ATS-friendly formatting
* Clear bullet points
* No company-specific information
* Do NOT invent salary, location, employment type, benefits or company details
* Return clean formatted text only."""
    return prompt


def generate_job_description(data: dict) -> str:
    """Generate a professional ATS-friendly job description using AI.

    Args:
        data: Dictionary with keys: department, job_title, experience,
              skills, additional_requirements.

    Returns:
        Generated job description text.
    """
    try:
        client = _get_jd_client()
        prompt = build_jd_prompt(data)

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": JD_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content or ""
        return raw.strip()

    except ValueError as e:
        logger.error("Job description AI service configuration error: %s", e)
        raise ValueError(str(e))
    except Exception as e:
        logger.exception("Job description generation request failed")
        raise RuntimeError(f"Failed to generate job description: {str(e)[:200]}")
