# Smart Task Assistant

An AI-powered FastAPI chat API for internal task management. Users send a single Arabic message to create a task, list tasks, or ask about company policy.

## Features

- **Single chat endpoint:** `POST /chat`, returning `action`, `task_id`, and an Arabic `reply`.
- **LLM-based intent extraction:** Uses Groq. The model is configurable through `CHAT_MODEL`; the sample configuration uses `openai/gpt-oss-120b`.
- **Backend-enforced authorization:** Roles and departments come from the employee database. The LLM cannot grant permissions or override a user's role.
- **Arabic date and time parsing:** Common relative dates and colloquial time expressions are handled in code. Ambiguous or invalid dates and times should trigger clarification rather than an invented schedule.
- **Friday scheduling rule:** Tasks requested for Friday are moved to Saturday at the same time, and the response explains the change.
- **Policy answers grounded in one source:** `app/data/company_policy.txt` is the source for company-policy answers. If the policy does not support an answer, the assistant should state that the information is unavailable.
- **SQLite and SQLAlchemy:** Database tables are initialized at application startup, and six demo employees are seeded automatically.
- **Persistent audit log:** Important chat operations are recorded in the SQLite `audit_logs` table without storing the original user message.
- **Docker support:** The application can run in a container with a persistent named volume for its SQLite database.
- **Automatic API documentation:** Swagger UI at `/docs` and a health endpoint at `/health`.

## How the request is handled

1. The API resolves `user_id` against the employee database.
2. The model classifies the message and extracts task details when needed.
3. The model output is validated before it reaches business logic.
4. Python services enforce authorization, task creation, date/time rules, and task-list visibility.
5. Policy questions are answered using `app/data/company_policy.txt` only.
6. The API records the operation in the audit log and returns the response.

Authorization checks live in code, particularly `app/services/authorization_service.py`, not in the prompt. For example, writing “I am the manager” in a message does not change the role stored in the database.

## Requirements

- Python 3.10 or newer
- Docker Desktop and Docker Compose v2 if using Docker
- A Groq API key: https://console.groq.com/keys

## Configuration

The application reads its configuration from environment variables.

| Variable | Purpose | Sample value |
|---|---|---|
| `GROQ_API_KEY` | API credential; keep it secret | `your_groq_api_key_here` |
| `CHAT_MODEL` | Groq model used for intent parsing and policy answers | `openai/gpt-oss-120b` |
| `APP_TIMEZONE` | Time zone used to interpret relative dates | `Asia/Riyadh` |
| `DATABASE_URL` | SQLAlchemy database connection | `sqlite:///./app_data/smart_tasks.db` |

Create a local `.env` file from `.env.example` and set your own `GROQ_API_KEY`. Never commit `.env` or expose a real API key.

The application creates its SQLite database and tables on startup if they do not exist. The local database may contain test data and must not be committed to Git.

## Setup without Docker

### Windows PowerShell

Run these commands from the project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder in `GROQ_API_KEY` with your own key. If `.env` already exists, keep your current local configuration instead of overwriting it.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and set `GROQ_API_KEY`. If `.env` already exists, do not overwrite it.

## Run the API locally

With the virtual environment activated, run:

```bash
python -m uvicorn app.main:app --reload
```

Open the following URLs:

- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

Expected health-check response:

```json
{
  "status": "ok"
}
```

The `--reload` option is intended for local development, not production deployment.

## Run with Docker

Make sure Docker Desktop is running and that a valid local `.env` file exists in the project root.

Validate the Compose configuration:

```powershell
docker compose config --quiet
```

Build the image and start the application:

```powershell
docker compose up -d --build
```

Check the container status:

```powershell
docker compose ps
```

Check the health endpoint:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Open Swagger UI at http://127.0.0.1:8000/docs.

### Docker database persistence

Docker uses the named volume `task_data`, mounted at `/app/app_data`, and the database connection:

```text
sqlite:////app/app_data/smart_tasks.db
```

This database is separate from the local database used when running the application directly with Python. Tasks and audit records stored in the Docker volume persist across container restarts.

Stop the application:

```powershell
docker compose stop
```

Start it again:

```powershell
docker compose up -d
```

**Warning:** `docker compose down -v` removes the named volume and its stored task and audit data. Do not use this command unless you intend to delete that data.

## API example

Send a `POST` request to `/chat` with JSON:

```json
{
  "user_id": 2,
  "message": "سجل مهمة لخالد بكرة الساعة عشرة يراجع عرض السعر"
}
```

A successful response has this shape; the actual task ID and date depend on the database and current date:

```json
{
  "action": "create_task",
  "task_id": 1,
  "reply": "تم تسجيل المهمة ..."
}
```

Possible `action` values:

- `create_task` — a task was created.
- `list_tasks` — a task list was returned.
- `policy_question` — the policy question was answered.
- `rejected` — the request was denied by authorization rules.
- `clarification` — more details are needed or the request is ambiguous.
- `error` — a service or configuration failure occurred.

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

These identities are for local assessment and demonstration use, not a production identity system.

## Permissions and behavior

- **Employee:** can create tasks for themselves only.
- **Supervisor:** can create tasks for employees in their own department.
- **Manager:** can create tasks for any employee.
- A user requesting their own tasks sees only their permitted tasks.
- Access to another employee's, a department's, or all tasks is controlled by backend authorization.
- A name not found in the employee database is not guessed; the assistant asks for clarification.
- A Friday due date moves to Saturday at the same time.
- If a policy answer is not explicitly supported by `app/data/company_policy.txt`, the assistant should say that the information is unavailable.
- Invalid or ambiguous scheduling details should trigger clarification instead of inventing a time.

## Audit logging

The application stores audit events in the persistent SQLite `audit_logs` table.

Each record can contain:

- `user_id` — the user associated with the operation, if known.
- `user_role` — the user's role, if known.
- `action` — the operation or response category, such as `list_tasks`, `create_task`, `rejected`, `clarification`, or `error`.
- `task_id` — the associated task ID, when applicable.
- `created_at` — the audit event timestamp, generated using the UTC clock.

The audit table does not store the original user message. The application also writes audit-style entries to its logger.

SQLite may display a stored timestamp without an explicit timezone suffix. Interpret the timestamp as UTC and convert it to the required local time zone when displaying it to users.

Audit logging is intended for this assessment prototype. A production deployment should define retention rules, access restrictions, monitoring, and failure-handling requirements for audit records.

## Run tests

The automated unit tests use controlled or mocked model outputs to make backend tests repeatable. They cover behavior such as authorization, date handling, Friday scheduling, response validation, and audit logging.

These tests do not, by themselves, measure real-world Arabic intent-extraction accuracy. They do not require a live Groq API key.

Run the local test suite:

```powershell
pytest -q
```

The current test suite contains 57 tests.

### Run the ten assessment messages against the live API

Start the API first, either locally or with Docker. Open a second terminal in the project root and run:

```powershell
python scripts/run_ten_tests.py
```

This script uses the configured model and requires a valid API key and a reachable API server. It is separate from the mocked unit tests and may create additional task data in the database used by that server.

## Known limitations and production considerations

- The current request body accepts `user_id` directly, as required for the assessment. In a real deployment, derive identity from a verified login/session or signed access token; do not trust a client-supplied ID.
- Demo users are seeded at startup. A production system should use controlled user provisioning and database migrations.
- SQLite and the current audit table are suitable for this prototype; production workloads may require a managed database and a formal migration strategy.
- Audit timestamps are generated in UTC. Convert them to the relevant local time zone when presenting them to users.
- `--reload` is for local development, not production deployment.
- The application depends on the configured Groq model being available to the account. Model access and pricing may change.

More implementation assumptions, workload estimates, cost estimates, and proposed next steps are documented in [DECISIONS.md](DECISIONS.md).


## Telegram Bot

The project supports linking individual Telegram accounts to employee records.
After a successful link, the bot resolves the employee from the stored Telegram
account link. Employees do not need to enter their employee ID with each
message.

### Configuration

Add the following variables to your local `.env` file:

- `TELEGRAM_BOT_TOKEN`: Bot token obtained from BotFather.
- `TELEGRAM_INTERNAL_TOKEN`: Shared secret used by the bot to call the
  protected internal Telegram endpoints.
- `TELEGRAM_LINK_ADMIN_TOKEN`: Secret required to issue employee linking codes.
- `TELEGRAM_API_URL`: Chat API URL. The Docker Compose bot service uses
  `http://api:8000/chat` inside the Compose network.

Keep real credentials in `.env` only. Never commit `.env` or paste secret
values into source code, documentation, screenshots, or unredacted logs.
Use `.env.example` as a template without real secret values.

### Run with Docker

From the project directory:

```powershell
docker compose up -d --build
docker compose ps
```

The Compose services are:

- `api`: FastAPI application.
- `bot`: Telegram polling bot.

To inspect recent API logs:

```powershell
docker compose logs --tail 30 api
```

Telegram bot logs may contain bot-token URLs. Review and redact secrets before
sharing logs.

### Link an Employee

1. An authorized administrator issues a linking code for an existing employee
   through `POST /telegram/issue-code`, authenticated with
   `TELEGRAM_LINK_ADMIN_TOKEN` as a Bearer token. The request body contains
   `employee_id`.
2. The linking code contains exactly 6 digits, expires after 10 minutes,
   and can be used successfully only once. Five failed attempts for the
   same Telegram account trigger a temporary 10-minute lock.
3. The employee opens the bot in a private Telegram chat and sends:

   `/link CODE`

   Replace `CODE` with the actual code. Do not share the code publicly.
4. The bot submits the Telegram account ID and code to the protected
   `POST /telegram/link` endpoint.
5. After linking, the bot resolves the employee through
   `POST /telegram/resolve` for subsequent messages.

The link is stored in the database, so deleting the Telegram conversation
does not remove the saved account link. A new Telegram account must be linked
separately.

### Telegram Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/telegram/issue-code` | Issue a linking code for an employee; admin token required. |
| `POST` | `/telegram/link` | Redeem a code to link a Telegram account; internal token required. |
| `POST` | `/telegram/resolve` | Resolve a linked Telegram account to an employee; internal token required. |

Do not expose internal or administrative endpoints publicly without
appropriate authentication, access controls, and rate limiting.
