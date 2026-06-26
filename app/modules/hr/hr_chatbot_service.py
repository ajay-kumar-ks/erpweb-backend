"""
HR Chatbot AI Service.

Conversational AI that answers user questions about HR data only.
Uses the same LLM infrastructure (OpenRouter/Gemini) as the CRM chatbot.
Falls back to rule-based responses when AI is unavailable.
"""
from openai import OpenAI
from app.core.config import settings

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
        print("[hr_chatbot] GEMINI_API_KEY is not set — Gemini AI features will use fallback")
except (ImportError, Exception) as e:
    _genai_available = False
    _genai_model = None
    print(f"[hr_chatbot] Gemini could not be initialized — Gemini fallback enabled. Error: {e}")

try:
    if settings.OPENROUTER_API_KEY:
        _openrouter_available = True
    else:
        print("[hr_chatbot] OPENROUTER_API_KEY is not set — OpenRouter AI features will use rule-based fallback")
except Exception as e:
    _openrouter_available = False
    print(f"[hr_chatbot] OpenRouter configuration check failed — fallback enabled. Error: {e}")


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

        print(f"[hr_chatbot] OpenRouter base_url={base_url}")
        _openrouter_client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://business-suite.local",
                "X-Title": "Business Suite - HR Assistant",
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
            print(f"[hr_chatbot] Gemini request sent. Raw response: {text!r}")
            if text:
                return text
        except Exception as e:
            err_msg = str(e)
            print(f"[hr_chatbot] Gemini call error ({type(e).__name__}): {err_msg}")
            if "429" in err_msg or "quota" in err_msg.lower():
                print("[hr_chatbot] Gemini quota issue detected, disabling Gemini for subsequent requests.")
                _genai_available = False

    if _openrouter_available:
        try:
            client = _get_openrouter_client()
            normalized_base_url = _normalize_openrouter_base_url(settings.OPENROUTER_BASE_URL)
            print(f"[hr_chatbot] Sending OpenRouter request to {normalized_base_url}")
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )
            text = response.choices[0].message.content.strip() if response and response.choices else None
            print(f"[hr_chatbot] OpenRouter request sent. Raw response: {text!r}")
            return text or None
        except Exception as e:
            print(f"[hr_chatbot] OpenRouter call error ({type(e).__name__}): {e}")
            if getattr(e, '__cause__', None):
                print(f"[hr_chatbot] OpenRouter root cause: {type(e.__cause__).__name__}: {e.__cause__}")

    return None


# ──────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful HR assistant for Business Suite. You ONLY answer questions about the HR data provided below.

If the user asks about something outside HR (e.g. CRM, accounting, tasks), politely say you can only assist with HR-related questions.

Available HR data categories:
- Employees (with departments, salaries, status, joining dates)
- Departments
- Attendance records (check-in/out, present/absent)
- Leave requests (pending, approved, rejected)
- Recruitment candidates (stages, status)
- Users (auth system users with admin status)

Rules:
- Answer conversationally and helpfully
- Keep answers concise but informative
- If you don't have data on something, suggest what the user can do in the HR module
- Use data provided below to give specific, accurate answers
- Never make up data — if the data says "No records" or "None", say so"""


# ──────────────────────────────────────────────
# Data summarizers
# ──────────────────────────────────────────────


def _summarize_employees(employees: list[dict]) -> str:
    if not employees:
        return "No employees in the system."
    lines = []
    for emp in employees[:30]:
        dept = emp.get("department_name", emp.get("department", "")) or "N/A"
        salary = emp.get("salary")
        salary_str = f"${salary:,.0f}" if salary else "N/A"
        status = emp.get("status", "Active")
        lines.append(
            f"- {emp.get('employee_code', 'N/A')} | Name: {emp.get('user_name', 'N/A')} | "
            f"Dept: {dept} | Salary: {salary_str} | Status: {status}"
        )
    if len(employees) > 30:
        lines.append(f"... and {len(employees) - 30} more")
    return "\n".join(lines)


def _summarize_departments(departments: list[dict]) -> str:
    if not departments:
        return "No departments configured."
    lines = []
    for dept in departments:
        desc = dept.get("description") or ""
        lines.append(f"- {dept.get('name', 'Unnamed')} | Description: {desc[:80]}")
    return "\n".join(lines)


def _summarize_attendance(attendance_records: list[dict]) -> str:
    if not attendance_records:
        return "No attendance records."
    lines = []
    for rec in attendance_records[:15]:
        emp_name = rec.get("employee_name", rec.get("employee_code", "N/A"))
        check_in = str(rec.get("check_in", ""))[:16] if rec.get("check_in") else "-"
        check_out = str(rec.get("check_out", ""))[:16] if rec.get("check_out") else "-"
        lines.append(
            f"- {emp_name} | Date: {rec.get('date', 'N/A')} | "
            f"In: {check_in} | Out: {check_out} | Status: {rec.get('status', 'N/A')}"
        )
    return "\n".join(lines)


def _summarize_leaves(leaves: list[dict]) -> str:
    if not leaves:
        return "No leave requests."
    lines = []
    for leave in leaves[:15]:
        emp_name = leave.get("employee_name", leave.get("employee_code", "N/A"))
        lines.append(
            f"- {emp_name} | Type: {leave.get('leave_type', 'N/A')} | "
            f"From: {leave.get('start_date', 'N/A')} To: {leave.get('end_date', 'N/A')} | "
            f"Status: {leave.get('status', 'N/A')}"
        )
    return "\n".join(lines)


def _summarize_candidates(candidates: list[dict]) -> str:
    if not candidates:
        return "No candidates in the recruitment pipeline."
    lines = []
    for c in candidates[:15]:
        dept = c.get("department_name", "") or "N/A"
        lines.append(
            f"- {c.get('full_name', 'N/A')} | Dept: {dept} | "
            f"Stage: {c.get('current_stage', 'N/A')} | Status: {c.get('status', 'N/A')}"
        )
    if len(candidates) > 15:
        lines.append(f"... and {len(candidates) - 15} more")
    return "\n".join(lines)


def _summarize_users(users: list[dict]) -> str:
    if not users:
        return "No auth users in the system."
    lines = []
    for u in users:
        admin_str = "Admin" if u.get("is_admin") else "User"
        lines.append(f"- {u.get('username', 'N/A')} | Name: {u.get('full_name', '-')} | Email: {u.get('email', '-')} | Role: {admin_str}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Data-driven fallback for simple queries
# ──────────────────────────────────────────────


def _hr_chatbot_data_fallback(
    message: str,
    employees: list[dict],
    departments: list[dict],
    attendance_records: list[dict],
    leaves: list[dict],
    candidates: list[dict],
    users: list[dict],
) -> str | None:
    """Try to answer simple, data-driven HR questions without AI.
    Returns a string answer when the query can be satisfied from the provided
    data, otherwise returns None to allow higher-level fallback.
    """
    q = (message or "").strip().lower()

    # ── Count queries ──
    if q.startswith("how many") or q.startswith("count") or "how many" in q:
        if "employee" in q or "people" in q or "staff" in q or "workers" in q:
            active = sum(1 for e in employees if e.get("status") == "Active")
            return f"There are {len(employees)} employee(s) total, with {active} currently active."

        if "department" in q:
            return f"There are {len(departments)} department(s) configured."

        if "candidate" in q or "applicant" in q or "recruit" in q:
            active_candidates = sum(1 for c in candidates if c.get("status") not in ("rejected", "onboarded", "converted"))
            return f"There are {len(candidates)} candidate(s) in the pipeline, with {active_candidates} still in progress."

        if "leave" in q or "absence" in q or "time off" in q:
            pending = sum(1 for l in leaves if l.get("status") == "Pending")
            approved = sum(1 for l in leaves if l.get("status") == "Approved")
            return f"There are {len(leaves)} leave request(s): {pending} pending, {approved} approved."

        if "attendance" in q or "present" in q:
            total = len(attendance_records)
            present = sum(1 for r in attendance_records if r.get("status") == "Present")
            absent = sum(1 for r in attendance_records if r.get("status") == "Absent")
            return f"There are {total} attendance records: {present} present, {absent} absent."

        if "user" in q or "login" in q:
            admins = sum(1 for u in users if u.get("is_admin"))
            return f"There are {len(users)} user(s), with {admins} admin(s)."

    # ── List/Show queries ──
    if any(word in q for word in ["list", "show", "what", "which", "who", "all"]) and any(
        word in q for word in ["employee", "department", "candidate", "leave", "user", "admin"]
    ):
        if "department" in q:
            if not departments:
                return "No departments configured yet."
            names = [d.get("name", "Unnamed") for d in departments]
            return "Departments:\n- " + "\n- ".join(names)

        if "admin" in q or ("user" in q and "admin" in q):
            admins = [u for u in users if u.get("is_admin")]
            if not admins:
                return "There are no admin users."
            admin_lines = [f"- {a.get('username', 'N/A')} ({a.get('full_name', '-')})" for a in admins]
            return "Admin users:\n" + "\n".join(admin_lines)

    # ── Salary queries ──
    if "salary" in q or "pay" in q or "compensation" in q:
        salaries = [e.get("salary") for e in employees if e.get("salary") is not None]
        if not salaries:
            return "No salary data available."
        avg = sum(salaries) / len(salaries)
        highest = max(salaries)
        lowest = min(salaries)
        return (f"Salary summary across {len(salaries)} employee(s):\n"
                f"- Average: ${avg:,.0f}\n"
                f"- Highest: ${highest:,.0f}\n"
                f"- Lowest: ${lowest:,.0f}")

    # ── Attendance today ──
    if "today" in q and ("attendance" in q or "present" in q or "absent" in q):
        from datetime import date
        today_str = str(date.today())
        today_records = [r for r in attendance_records if str(r.get("date", "")) == today_str]
        present = sum(1 for r in today_records if r.get("status") == "Present")
        absent = sum(1 for r in today_records if r.get("status") == "Absent")
        return f"Today's attendance: {present} present, {absent} absent (out of {len(today_records)} records)."

    return None


# ──────────────────────────────────────────────
# Generic fallback
# ──────────────────────────────────────────────


def _hr_chatbot_fallback(message: str) -> str:
    """Fallback response when AI is unavailable."""
    msg_lower = message.lower()

    if any(word in msg_lower for word in ["hello", "hi", "hey", "greetings"]):
        return ("Hello! I'm your HR assistant. I can help you with employees, departments, "
                "attendance, leaves, recruitment, and user management. What would you like to know?")

    if any(word in msg_lower for word in ["employee", "staff", "worker", "personnel"]):
        return ("I can help with employee information. You can view employee records, "
                "department assignments, salaries, and status. Try asking 'How many employees do I have?' "
                "or 'Show me employees in a specific department.'")

    if any(word in msg_lower for word in ["attendance", "present", "absent", "check.in", "checkin"]):
        return ("I can help with attendance data. You can check who's present today, "
                "view attendance records, and see trends. Try asking 'Who's present today?' "
                "or 'How many attendance records are there?'")

    if any(word in msg_lower for word in ["leave", "vacation", "time off", "absence", "sick"]):
        return ("I can help with leave management. You can check leave requests, approvals, "
                "and balances. Try asking 'How many pending leaves are there?' "
                "or 'Show me leave requests.'")

    if any(word in msg_lower for word in ["recruit", "candidate", "applicant", "hiring", "pipeline"]):
        return ("I can help with recruitment. You can track candidates through pipeline stages. "
                "Try asking 'How many candidates are in the pipeline?' "
                "or 'Show me candidates in Interview stage.'")

    if any(word in msg_lower for word in ["department", "team", "division"]):
        return ("I can help with department information. Try asking 'What departments exist?' "
                "or 'How many employees are in each department?'")

    if any(word in msg_lower for word in ["user", "admin", "login", "account"]):
        return ("I can help with user management. Try asking 'How many users are there?' "
                "or 'Who are the admin users?'")

    if any(word in msg_lower for word in ["salary", "pay", "compensation"]):
        return ("I can help with salary information. Try asking 'What's the average salary?' "
                "or 'Show me salary details.'")

    return ("I'm your HR assistant. I can answer questions about your employees, departments, "
            "attendance, leaves, recruitment candidates, and users. What would you like to know?")


# ──────────────────────────────────────────────
# Main chatbot function
# ──────────────────────────────────────────────


def hr_chatbot(
    message: str,
    history: list[dict],
    employees: list[dict],
    departments: list[dict],
    attendance_records: list[dict],
    leaves: list[dict],
    candidates: list[dict],
    users: list[dict],
) -> str:
    """
    HR Chatbot: Answers user questions about HR data only.
    Uses AI with full HR context to answer questions.
    Falls back to a rule-based response if AI is unavailable.
    """
    if not (_genai_available or _openrouter_available):
        print("[hr_chatbot] AI not available, using fallback")
        # Try data-driven fallback first
        data_answer = _hr_chatbot_data_fallback(
            message=message,
            employees=employees,
            departments=departments,
            attendance_records=attendance_records,
            leaves=leaves,
            candidates=candidates,
            users=users,
        )
        if data_answer:
            print("[hr_chatbot] Data-driven fallback answered the query.")
            return data_answer
        return _hr_chatbot_fallback(message)

    # Build a compact summary of HR data
    emp_summary = _summarize_employees(employees)
    dept_summary = _summarize_departments(departments)
    att_summary = _summarize_attendance(attendance_records)
    leave_summary = _summarize_leaves(leaves)
    cand_summary = _summarize_candidates(candidates)
    user_summary = _summarize_users(users)

    # Build conversation history
    history_text = ""
    for h in history[-10:]:  # last 10 messages for context
        role = "User" if h.get("role") == "user" else "Assistant"
        content = (h.get("content", "") or "")[:500]
        history_text += f"{role}: {content}\n"

    prompt = f"""{SYSTEM_PROMPT}

Available HR data:

=== EMPLOYEES ({len(employees)} total) ===
{emp_summary}

=== DEPARTMENTS ({len(departments)} total) ===
{dept_summary}

=== ATTENDANCE ({len(attendance_records)} total) ===
{att_summary}

=== LEAVE REQUESTS ({len(leaves)} total) ===
{leave_summary}

=== RECRUITMENT CANDIDATES ({len(candidates)} total) ===
{cand_summary}

=== USERS ({len(users)} total) ===
{user_summary}

---
Previous conversation:
{history_text}

User: {message}

Respond conversationally and helpfully. Keep answers concise but informative. If the user asks for something you don't have data on, suggest what they can do in the HR module.
Assistant:"""

    text = _call_llm(prompt)
    if text:
        return text[:2000]

    # Try deterministic data-driven fallback
    data_answer = _hr_chatbot_data_fallback(
        message=message,
        employees=employees,
        departments=departments,
        attendance_records=attendance_records,
        leaves=leaves,
        candidates=candidates,
        users=users,
    )
    if data_answer:
        print("[hr_chatbot] Data-driven fallback answered the query.")
        return data_answer

    return _hr_chatbot_fallback(message)
