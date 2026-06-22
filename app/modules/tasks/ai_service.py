"""
AI-powered task suggestions service.

Connects to OpenRouter (OpenAI-compatible API) to provide:
  - Suggested subtasks / checklist items
  - Suggested dependencies
  - Suggested assignee
  - Suggested priority
  - Estimated effort in hours
"""

import json
import logging
from typing import Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Client initialisation
# ──────────────────────────────────────────────

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    """Lazy-init the OpenAI client pointed at OpenRouter."""
    global _client
    if _client is None:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is not configured. "
                "Set it in your .env file."
            )
        _client = OpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - Task AI Assistant",
            },
        )
    return _client


# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a highly experienced project manager and task-planning AI assistant for a business management suite.

Your job is to analyse task titles and produce structured suggestions that help the user plan their tasks better.

Respond ONLY with valid JSON — no markdown, no explanations. The JSON object must have exactly these keys:
```json
{
  "suggested_description": "string | null",
  "subtasks": ["string", ...],
  "dependencies": ["string", ...],
  "suggested_assignee": "string | null",
  "suggested_priority": "LOW | MEDIUM | HIGH | URGENT",
  "estimated_effort_hours": number | null,
  "explanation": "string"
}
```

Rules:
0. **suggested_description** — Write a clear, detailed description (2-3 sentences) explaining what needs to be done. Include key requirements and acceptance criteria if they can be inferred from the title. Use null if the title is too vague.
1. **subtasks** — Suggest 2-5 concrete checklist items that break down the task. Keep each item short (5-10 words).
2. **dependencies** — Suggest 0-3 things that likely need to be done first (e.g. "Design approval", "Backend API ready", "Stakeholder sign-off").
3. **suggested_assignee** — Based on the task, suggest a role/department (e.g. "Backend Developer", "UI/UX Designer", "Marketing Lead", "DevOps Engineer"). Use null if unclear.
4. **suggested_priority** — Based on urgency indicators. Be conservative — default to MEDIUM unless keywords like "urgent", "critical", "asap", "blocker", "security" appear.
5. **estimated_effort_hours** — Estimate a realistic number of hours (1-80). Use null if the task is too vague. Consider: adding a simple button = 2-4h, building an API endpoint = 4-8h, full feature = 16-40h.
6. **explanation** — A short, friendly sentence explaining the reasoning behind the suggestions.
"""


# ──────────────────────────────────────────────
# Public helpers
# ──────────────────────────────────────────────


def build_task_context(title: str, description: Optional[str] = None) -> str:
    """Build a concise task context string for the AI prompt."""
    parts = [f"Title: {title}"]
    if description and description.strip():
        parts.append(f"Description: {description.strip()}")
    return "\n".join(parts)


def parse_ai_response(raw: str) -> dict:
    """Try to extract a JSON object from the AI response, with resilience."""
    # Strip any markdown fences
    text = raw.strip()
    if text.startswith("```"):
        # Remove opening fence (possibly with language hint)
        first_nl = text.find("\n")
        if first_nl != -1:
            text = text[first_nl:].strip()
        # Remove closing fence
        if text.endswith("```"):
            text = text[:-3].strip()

    # Try to parse directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object anywhere in the text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.warning("Failed to parse AI response as JSON:\n%s", raw)
        return {
            "suggested_description": None,
            "subtasks": [],
            "dependencies": [],
            "suggested_assignee": None,
            "suggested_priority": "MEDIUM",
            "estimated_effort_hours": None,
            "explanation": "Could not generate suggestions at this time.",
        }


# ──────────────────────────────────────────────
# Main suggestion function
# ──────────────────────────────────────────────

def get_task_suggestions(title: str, description: Optional[str] = None) -> dict:
    """Get AI-powered suggestions for a task.

    Returns a dict with keys:
      - suggested_description (str | None)
      - subtasks (list[str])
      - dependencies (list[str])
      - suggested_assignee (str | None)
      - suggested_priority (str)
      - estimated_effort_hours (int | None)
      - explanation (str)
    """
    try:
        client = _get_client()
        context = build_task_context(title, description)

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",  # fast & cheap model available on OpenRouter
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyse this task and provide suggestions:\n\n{context}"},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content or ""
        result = parse_ai_response(raw)

        # Validate and normalise fields
        if not isinstance(result.get("subtasks"), list):
            result["subtasks"] = []
        if not isinstance(result.get("dependencies"), list):
            result["dependencies"] = []
        if result.get("suggested_priority") not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
            result["suggested_priority"] = "MEDIUM"
        if not isinstance(result.get("estimated_effort_hours"), (int, float)):
            result["estimated_effort_hours"] = None
        else:
            result["estimated_effort_hours"] = round(result["estimated_effort_hours"])
        if not isinstance(result.get("suggested_description"), str):
            result["suggested_description"] = None

        return result

    except ValueError as e:
        logger.error("AI service configuration error: %s", e)
        return {
            "suggested_description": None,
            "subtasks": [],
            "dependencies": [],
            "suggested_assignee": None,
            "suggested_priority": "MEDIUM",
            "estimated_effort_hours": None,
            "explanation": f"Configuration error: {e}",
        }
    except Exception as e:
        logger.exception("AI suggestion request failed")
        return {
            "suggested_description": None,
            "subtasks": [],
            "dependencies": [],
            "suggested_assignee": None,
            "suggested_priority": "MEDIUM",
            "estimated_effort_hours": None,
            "explanation": f"Sorry, I couldn't generate suggestions right now. Error: {str(e)[:100]}",
        }
