






#####Main rule of this project, print out the code in small chunks with explanation, i mean one function  at a time , explain it to a 2nd year cs student, the purpose is to make me undesratnd every little ddetail of how it works######












Python Rewrite Roadmap
Why this document
Move the current Node/TypeScript app to Python.
Keep the same functionality: leads → validation → phases → Twilio calls → ElevenLabs realtime → transcript storage → viewing booking → progression.
No code here, only implementation steps, checklists, and acceptance criteria.
1) Goals and success criteria
Replace the Node app with a Python service providing identical APIs and behavior.
Keep DB schema and data intact (Sequelize → SQLAlchemy), including confirmation flags and enum constraints.
Maintain call quality and latency (pre-warming ElevenLabs).
Support transcript storage webhook at end-of-call; progression can be handled by internal logic using stored data.
Green E2E tests for:
Creating a lead via webhook
Call connects and agent talks
Agent confirms data and updates once at end
Viewing booking stored and linked to lead
Phases advance correctly
2) Tech stack choices
Web framework: FastAPI (async, great docs, Pydantic validation).
ORM: SQLAlchemy 2.0 + Alembic for migrations.
Validation: Pydantic models.
WebSockets: FastAPI’s WebSocket support or websockets client for ElevenLabs.
Telephony: Twilio Python SDK and TwiML webhooks.
Realtime voice: ElevenLabs Realtime via WebSocket API (Python client or raw WS).
Background tasks: FastAPI BackgroundTasks or a lightweight task runner (RQ/Celery if needed later).
Tunneling/local testing: ngrok.
Observability: Python logging, structured logs, Sentry (optional).
Packaging: uv/poetry/pip-tools (choose one) + Docker for deployment.
3) System architecture (high-level)
API layer (FastAPI):
 Public webhook: receive lead data (with secret).
 Transcript webhook: store call transcript at end-of-call.
 Twilio webhooks: voice and call-status.
 Health/readiness.
Services:
LeadService: validate input, create/update leads, phase logic, confirmation checks.
CallService: place calls via Twilio, manage delays, callbacks.
ElevenLabsSession: manage realtime WS, pre-warm connections map, build agent context.
ViewingService: create viewing records linked to lead.
Database:
Leads table with confirmation flags and contract length enum constraint.
PropertyViewing table.
Realtime:
Pre-warmed ElevenLabs connections keyed by lead ID.
Use if available at call start; otherwise establish fresh.
4) Project structure
app/
api/ (routers: leads, agent-tools, twilio, health)
services/ (lead, call, viewing, elevenlabs_prewarm, session)
db/ (models, migrations, session management)
schemas/ (pydantic input/output)
core/ (config, logging, settings)
tests/
unit, integration, e2e
scripts/
local test helpers (no secrets)
Dockerfile, compose for dev DB.
5) Environment and configuration
Define env vars:
DATABASE_URL (Postgres)
WEBHOOK_SECRET (lead data authentication)
TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
PUBLIC_BASE_URL (for Twilio callbacks; points to ngrok in dev)
ELEVENLABS_API_KEY, ELEVENLABS_AGENT_URL/WS endpoint
Add a single settings module to read and validate env.
Acceptance:
Running the app with missing env shows clear errors.
Health endpoint returns 200 when DB connection works.
6) Database and migrations
Recreate the schema in SQLAlchemy models matching existing DB:
Leads: includes yearly_wage (integer), contract_length (string with check), *_confirmed booleans, viewing fields.
PropertyViewing: fields aligned with current app (including property_address, status).
Use Alembic to generate baseline migration that matches current live DB.
Verify constraints:
Contract length check values: LT_SIX_MONTHS, SIX_MONTHS, TWELVE_MONTHS, GT_TWELVE_MONTHS.
Confirmation columns default false.
Data migration plan:
If using the same DB, no data copy needed.
If new DB, export/import and re-apply constraints.
Acceptance:
Running migrations on a fresh DB yields identical schema.
Describing tables shows expected columns and constraints.
7) Domain models and validation
Pydantic input schemas for:
Lead webhook payload (with nested data): yearlyWage integer, contractLength enum (string), postcode min length 1, email optional.
Agent tool update payload: lead_id (string), confirm flags, optional occupation/yearly_wage/contract_length, optional viewing date/time/notes.
Conversion:
Map API names to DB column names (camelCase → snake_case).
Output schemas: consistent, include phase info and what changed.
Acceptance:
Validation rejects wrong types and gives helpful messages.
Valid payloads create/update without errors.
8) Lead service and phase logic
Required for CONFIRM_INFO: name, budget, move_in_date, occupation, yearly_wage (email excluded).
check_phase_requirements returns:
can_progress: true only if required fields are present and confirmed.
missing_fields, unconfirmed_fields, next_phase (if any).
update_lead_phase moves:
CONFIRM_INFO → BOOKING_VIEWING when requirements met.
BOOKING_VIEWING → VIEWING_BOOKED when viewing scheduled.
Confirmation logic:
Confirm flags set existing fields’ _confirmed true.
New data written is auto-confirmed.
Acceptance:
Unit tests cover edge cases (missing vs unconfirmed).
After final confirmation, phase advances.
9) HTTP endpoints
POST /webhook/lead-data (authenticated by header secret):
Validate payload.
Create lead.
Kick off pre-warm and schedule call (if configured).
POST /agent/update-lead:
Accept one-time end-of-call batch update.
Apply confirm flags and new data.
Create PropertyViewing if date+time given.
Recompute phase and return phase info.
POST /voice (TwiML):
Return TwiML to connect media stream to your WS bridge.
POST /call-status:
Record call lifecycle events (initiated, ringing, answered, completed).
GET /healthz and /readyz:
Report status.
Acceptance:
All routes reachable locally through ngrok HTTPS.
Auth on webhook enforced; others as required.
10) Twilio integration
Outbound call:
Disable Answering Machine Detection during testing to reduce delay.
Provide TwiML endpoint to connect stream immediately.
Media stream bridge:
Ensure audio WS is connected to ElevenLabs session when call answers.
Status callbacks:
Log transitions for debugging; correlate calls by lead_id.
Acceptance:
Call rings and connects; agent speaks quickly.
No unnecessary delays from AMD.
11) ElevenLabs realtime integration
Session manager:
Create WebSocket to ElevenLabs Realtime.
Send conversation initiation with dynamic variables (lead context).
Maintain connection state (connected, speaking).
Pre-warming service:
Map of pre-warmed WS sessions keyed by lead_id.
Lifecycle: create on lead creation; hand off at call start; cleanup on use/timeout.
Agent instructions:
Provide context: lead info, required fields, confirmation protocol.
Acceptance:
If pre-warmed, agent speaks near-instantly on answer.
12) Transcript webhook configuration
Definition in ElevenLabs dashboard (or integration):
Single webhook: send transcript at end-of-call.
Body fields: leadId (string), transcript (string).
Headers: Content-Type application/json.
Acceptance:
Webhook test from dashboard returns 200 locally via ngrok.
Real conversation sends transcript which is stored for the lead.
13) Viewing booking flow
When both viewing_date and viewing_time are present:
Save on lead and create PropertyViewing (status scheduled).
Include property address from lead if available.
Moving to VIEWING_BOOKED:
After successful creation.
Acceptance:
Viewing rows present and linked to the correct lead.
Phase shows VIEWING_BOOKED.
14) Observability and operations
Structured logs:
Correlate by lead_id and call_sid.
Log pre-warm lifecycle, tool calls, phase changes.
Error reporting:
Sentry or similar optional.
Health checks:
DB connection status in readiness probe.
Acceptance:
Logs show end-to-end flow for a test lead.
Health endpoints used by container orchestrator.
15) Testing strategy
Unit tests:
Validation, phase logic, confirmation transitions.
Integration tests:
DB CRUD, migrations up/down, transcript endpoint.
E2E happy path:
Create lead → pre-warm → call → transcript stored → viewing booked.
E2E edge cases:
Missing confirmations, invalid contract length, webhook timeout.
Acceptance:
CI runs all tests green.
E2E runs locally with ngrok and Twilio test numbers.
16) Security and compliance
Webhook secret check for lead-data endpoint.
Validate and sanitize all input.
Store minimal PII; secure env vars.
HTTPS enforced externally (ngrok, load balancer).
Acceptance:
Requests without valid secret are rejected.
Security checklist reviewed.
17) 17) Deployment
Deploy directly to Railway from GitHub.
Provide requirements.txt or pyproject.toml for dependencies.
Configure environment variables in Railway dashboard.
Database provisioned via Railway's Postgres addon.
Rollback plan:
Railway supports instant rollback to previous deployments.
Old Node app can continue if DB schema stays compatible.
Acceptance:
Push to main branch triggers Railway deployment.
Environment variables configured in Railway dashboard.
Health endpoints accessible via Railway's provided URL.
18) Cutover plan
Run both services in parallel (dark launch Python behind feature flag or on separate URL).
Smoke test:
Create a test lead; confirm full flow works on Python.
Switch traffic:
Update ngrok/Twilio webhooks to point at Python URL.
Monitor:
Logs, error rates, call quality.
Backout:
Re-point Twilio back to Node if needed.
Acceptance:
No regression in latency or success rates.
Tool updates saved reliably.
19) Risks and mitigations
Realtime audio timing differences:
Test pre-warm thoroughly; add connection fallbacks.
Tool call reliability:
Retries with idempotency via lead_id and timestamps (design decision).
Schema drift:
Lock schema in Alembic; compare with production before cutover.
20) Checklist per milestone
Milestone A: Project scaffold, settings, health checks.
Milestone B: DB models + Alembic baseline, validation schemas.
Milestone C: Lead webhook, LeadService, phase logic.
Milestone D: Transcript webhook endpoint and validation.
Milestone E: Twilio voice + status endpoints.
Milestone F: ElevenLabs session + pre-warm.
Milestone G: Viewing booking flow + phase advance.
Milestone H: Observability, E2E tests, docs.
Milestone I: Deploy, cutover, monitor.
21) Documentation to maintain
API contracts (endpoints, request/response shape).
Transcript webhook setup guide (dashboard fields, sample payload).
Runbook (starting services, rotating secrets, common failures).
Testing guide (how to run e2e locally with ngrok).
— End of roadmap —
Summary
Provided a full, code-free roadmap.md outlining architecture, stack, schema, endpoints, Twilio/ElevenLabs integration, confirmation flow, migrations, testing, deployment, and cutover.
Structured into clear phases with acceptance criteria and checklists to guide the Python rewrite end-to-end.








potential system prompts to add on  :# Environment

You are engaged in a phone conversation with a potential client.
Your goal is to gather information and book a property viewing.
You have access to a database of available properties and their schedules.
{{system__caller_id}} is the caller's phone number.
{{system__time_utc}} is the current UTC time.

# Tone

Your responses are clear, concise, and professional.
You use a friendly and helpful tone.
You avoid jargon and technical terms.
You speak at a moderate pace and enunciate clearly.
You use brief affirmations like "Okay," "Great," and "I understand" to show you are listening.
