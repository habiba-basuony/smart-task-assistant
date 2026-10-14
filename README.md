# Smart Task Assistant

A FastAPI chat API for an internal task-management workflow. Users send one Arabic message to create a task, list tasks, or ask about the company policy.

## Features

- **One chat endpoint:** `POST /chat`, returning `action`, `task_id`, and an Arabic `reply`.
- **LLM-based intent extraction:** Groq; model is configurable with `CHAT_MODEL` (the sample configuration uses `openai/gpt-oss-120b`).
- **Backend-enforced permissions:** the user's role and department come from the database. The LLM does not grant permissions or override a user's role.
- **Arabic date and time parsing:** common relative dates and colloquial time expressions are handled in code. Unclear or invalid dates/times should trigger clarification rather than creating a task with an invented time.
- **Friday rule:** a task requested for Friday is moved to Saturday at the same time, and the response explains the change.
- **Policy answers grounded in one file:** `app/data/company_policy.txt` is the source for company-policy answers. If the policy does not support an answer, the assistant is instructed to say the information is unavailable.
- **SQLite + SQLAlchemy:** the database and tables are initialized at application startup; six demo employees are seeded automatically.
- **Automatic API documentation:** Swagger UI at `/docs`, plus a lightweight `/health` endpoint.

## How the request is handled

1. The API resolves `user_id` against the employee database.
2. The model classifies the message and extracts task details when needed. The model output is validated before it reaches business logic.
3. Python services handle permissions, task creation, date/time rules, and listing scope.
4. Policy questions are answered from `app/data/company_policy.txt` only.

Authorization checks live in code (`app/services/authorization_service.py`), not in the prompt. For example, writing “I am the manager” in a message does not change the role stored in the database.

## Requirements

- Python 3.10 or newer
- A Groq API key: <https://console.groq.com/keys>

## Setup

### Windows PowerShell

Run these commands from the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder in `GROQ_API_KEY` with your own key. Keep `.env` private; do not commit it.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and set `GROQ_API_KEY`.

### Environment variables

| Variable | Purpose | Sample value |
|---|---|---|
| `GROQ_API_KEY` | API credential; keep it secret | `your_groq_api_key_here` |
| `CHAT_MODEL` | Groq model used for intent parsing and policy answers | `openai/gpt-oss-120b` |
| `APP_TIMEZONE` | Time zone used to interpret relative dates | `Asia/Riyadh` |
| `DATABASE_URL` | SQLAlchemy database connection | `sqlite:///./app_data/smart_tasks.db` |

The application creates the SQLite database and tables on startup if they do not exist. The database file contains local test data and should not be committed.

## Run the API

From the project root, with the virtual environment activated:

```bash
python -m uvicorn app.main:app --reload
```

Open:

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

Expected health-check response:

```json
{"status":"ok"}
```

## API example

Send a `POST` request to `/chat` with JSON:

```json
{
  "user_id": 2,
  "message": "سجل مهمة لخالد بكرة الساعة عشرة يراجع عرض السعر"
}
```

The exact reply and task ID depend on the database and current date. A successful task creation has this shape:

```json
{
  "action": "create_task",
  "task_id": 1,
  "reply": "تم تسجيل المهمة ..."
}
```

Possible `action` values:

- `create_task` — task created
- `list_tasks` — task list returned
- `policy_question` — answered from the company policy
- `rejected` — request denied by authorization rules
- `clarification` — more details are needed or the request is ambiguous
- `error` — a service/configuration failure

## Seeded demo users

On startup, the app creates these demo users if they are missing:

| `user_id` | Name | Role | Department |
|---:|---|---|---|
| 1 | منيرة | Manager | Admin |
| 2 | سارة | Supervisor | Projects |
| 3 | فهد | Employee | Projects |
| 4 | خالد | Employee | Projects |
| 5 | نورة | Employee | Finance |
| 6 | عبدالرحمن | Supervisor | Finance |

These identities are for local assessment/demo use, not a production identity system.

## Run tests

Unit tests use controlled/mock model outputs for repeatable tests of backend rules; they do **not**, by themselves, measure the real model's Arabic intent-extraction accuracy. They do not need a live Groq API key.

```bash
python -m pytest -q
```

To run the ten assessment messages against a server that is already running (this uses the configured model and requires a valid API key), open a second terminal in the project root and run:

```bash
python scripts/run_ten_tests.py
```

## Permission and behavior summary

- **Employee:** can create tasks for themselves only.
- **Supervisor:** can create tasks for employees in their own department.
- **Manager:** can create tasks for any employee.
- “My tasks” returns the sender's own tasks. Access to another person's, department's, or all tasks is governed by backend authorization.
- A name not found in the employee database is not guessed; the user is asked to clarify.
- A Friday due date moves to Saturday at the same time.
- If a policy answer is not explicitly supported by `app/data/company_policy.txt`, the assistant should say that the information is unavailable.

## Known limitations / production considerations

- The current request body accepts `user_id` directly, as required for the assessment. In a real deployment, derive identity from a verified login/session or signed access token; do not trust a client-supplied ID.
- Basic audit-style action entries are written to the application log. They are not yet stored in a dedicated persistent audit table.
- Demo users are seeded on startup; a production system should use controlled user provisioning and database migrations.
- `--reload` is for local development, not production deployment.

More implementation assumptions, workload estimates, and proposed next steps are documented in [`DECISIONS.md`](DECISIONS.md).
