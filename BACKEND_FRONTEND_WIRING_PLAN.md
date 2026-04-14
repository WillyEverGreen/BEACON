# BEACON — Frontend-Backend Wiring Plan

**Revision:** April 2026  
**Goal:** Wire the frontend dashboard to FastAPI end-to-end, with full support for both **AI-disabled mode** (deterministic scoring only) and **AI-enabled mode** (LLM fix suggestions + RAG pipeline active).

---

## Guiding Principle: The AI Layer Is Optional Infrastructure

The application must be fully functional without the AI layer. Every scan, score, issue list, project CRUD operation, and dashboard view works in both modes. The AI layer adds enrichment — it does not gate core functionality.

```
┌─────────────────────────────────────────────────────────────────┐
│  BEACON Core (always on)                                        │
│  axe-core + custom checks + Playwright probes + scoring engine  │
│  FastAPI dashboard API + auth + projects/scans CRUD             │
└─────────────────────────────────────────────────────────────────┘
           ↑ optional enrichment only
┌─────────────────────────────────────────────────────────────────┐
│  AI Layer (feature-flagged, gracefully degraded)                │
│  RAG pipeline (ChromaDB + BM25 + CrossEncoder)                  │
│  LLM fix suggestions (Featherless / Qwen2.5-Coder-32B)          │
│  /rag endpoint + /audit?mode=ai                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Design rule:** any component that calls the AI layer must handle a disabled/unavailable state without throwing, blocking a render, or hiding non-AI data from the user.

### Async Execution Model

Scans and AI enrichment must never block the API thread. The execution model is:

```
POST /v1/api/scans/
  └── API thread: validate, create DB record, enqueue job → return 202 immediately
        └── Background worker: run scan (axe + Playwright + scoring)
              └── On completion: if AI enabled, enqueue AI enrichment job (separate)
                    └── AI worker: RAG query + LLM suggestions → write to DB
                          └── Frontend polls /progress → picks up results when ready
```

**Worker strategy — choose one and document it:**

| Option                    | When to use                                     | Notes                                   |
| ------------------------- | ----------------------------------------------- | --------------------------------------- |
| `FastAPI BackgroundTasks` | Solo developer, low concurrency (≤5 scans)      | No extra infra. Fine for now.           |
| `RQ` (Redis Queue)        | When you need retry logic or job visibility     | Lightweight. Good next step.            |
| `Celery`                  | Multi-worker, high concurrency, priority queues | Only when you have paying users waiting |

**Current recommendation for BEACON:** Use `FastAPI BackgroundTasks` now. Add `RQ` when you have more than one concurrent user. Do not install Celery until you need it.

**Rules regardless of worker choice:**

- Scan execution must never block the API thread
- AI enrichment runs as a separate post-scan async job, triggered only after core scan completes successfully
- If the AI enrichment job fails, the scan record stays in `completed` state — only the `fix_suggestions` field is absent
- Job status is readable via the `/progress` endpoint without polling the worker directly

### Job Status States

Every scan record moves through these states exactly once in order:

```
pending → running → completed
                 └→ failed
```

Extended states when AI layer is enabled:

```
pending → running → completed_without_ai   (core done, AI enrichment skipped/failed)
                 └→ completed_with_ai      (core done + suggestions written to DB)
                 └→ failed                 (core scan itself failed)
```

The `/progress` endpoint always returns the current `status` field. Frontend behavior per state:

| Status                                                     | UI behavior                            |
| ---------------------------------------------------------- | -------------------------------------- |
| `pending`                                                  | "Queued..." spinner                    |
| `running`                                                  | Progress bar, poll every 3s            |
| `completed` / `completed_with_ai` / `completed_without_ai` | Show results, stop polling             |
| `failed`                                                   | Show error message, offer retry button |

### Retry Policy

Not all failures are equal. Retry only transient failures.

```
Transient (retry):        network timeout, upstream 5xx, Playwright launch failure
Deterministic (no retry): invalid URL (4xx), malformed scan config, auth failure

Retry schedule:
  Attempt 1 → immediate
  Attempt 2 → 1s delay
  Attempt 3 → 5s delay
  Attempt 4 → 15s delay → mark as failed, no further retries

AI enrichment job uses the same policy independently of the core scan job.
```

When `max_retries` is exhausted: set status to `failed`, write `error_code` and `error_message` to the scan record, log the final exception with `request_id`.

### Scan Timeout Behavior

A scan that never finishes is worse than a scan that fails cleanly.

```
Max scan duration:  180 seconds (3 minutes)
Max AI enrichment:   60 seconds (separate timeout)
```

When the core scan exceeds 180s:

- Background worker cancels the Playwright session
- Scan record status → `failed`
- `error_code: "scan_timeout"`, `error_message: "Scan exceeded maximum duration of 3 minutes"`
- Frontend shows: "This scan took too long and was stopped. This can happen with slow or JavaScript-heavy pages. Try again or check the URL."
- Retry button available — counts against the user's daily quota

When AI enrichment exceeds 60s:

- AI job is cancelled silently
- Scan status → `completed_without_ai`
- No error shown to user — fix suggestions simply absent

---

## Canonical Architecture Decision

**FastAPI is the single backend source of truth for all frontend data flows.**

- Frontend routes already align with FastAPI dashboard endpoints.
- Node layer (server.js) has a different async job contract and introduces drift risk.
- Node disposition: move to port `3001` as a legacy compatibility layer with an explicit sunset date. All new frontend code targets FastAPI only.

---

## Environment Modes

| Mode        | `BEACON_AI_ENABLED`            | LLM calls fire       | RAG queries fire | Core scan |
| ----------- | ------------------------------ | -------------------- | ---------------- | --------- |
| Core-only   | `false`                        | No                   | No               | Yes       |
| AI-enabled  | `true`                         | Yes (≤15% of issues) | Yes              | Yes       |
| AI degraded | `true` but LLM/RAG unreachable | Skipped silently     | Skipped silently | Yes       |

The frontend reads `BEACON_AI_ENABLED` from the BFF (never directly from env in client JS). Issue cards render fix suggestions if the field is present; they render without them otherwise — no spinners left hanging.

---

## Phase 0 — Baseline Freeze

**Day 1 morning | Blocker for everything else**

### Deliverables

- Integration branch: `integration/frontend-backend-wireup`
- Baseline smoke results captured and committed
- Ports locked: FastAPI `8000`, Next `3000`, Node `3001`
- Git tag: `wireup-baseline`

### Tasks

1. Record working behavior for:
   - `GET /health` — assert `{"status": "ok"}`
   - `GET /api/projects/` — assert list (may be empty)
   - create project → start scan → poll progress → completed state
   - `GET /health` with `BEACON_AI_ENABLED=false` — confirm core path returns same shape
   - `GET /health` with `BEACON_AI_ENABLED=true` — confirm AI services reachable flag present
2. Capture both AI-on and AI-off baseline states separately. Both must pass before proceeding.
3. Lock port assignments and commit `.env.example` values.
4. Tag baseline commit.

### Exit Criteria

- Team can reproduce AI-off and AI-on baseline in one command set each.
- Any deviation from baseline is a regression, not a "known issue."

---

## Phase 0.5 — Developer Ergonomics

**Day 1 morning | Parallel with Phase 0**

### Deliverables

- One-command local startup
- Complete env templates — backend and frontend
- 5-minute quickstart in README
- Troubleshooting table

### Tasks

**One-command startup (Docker Compose preferred):**

```yaml
# docker-compose.yml outline
services:
  backend:
    build: .
    ports: ["8000:8000"]
    env_file: .env
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    env_file: ./frontend/.env
    depends_on: [backend]
  node-legacy:
    build: ./node
    ports: ["3001:3001"]
    profiles: ["legacy"] # opt-in only
  chromadb:
    image: chromadb/chroma
    profiles: ["ai"] # opt-in only, not required for core
```

Run core-only: `docker compose up`  
Run with AI layer: `docker compose --profile ai up`  
Run with legacy Node: `docker compose --profile legacy up`

**Frontend env template (`frontend/.env.example`):**

```
# BFF connection to FastAPI — never exposed to browser JS
BEACON_API_BASE_URL=http://localhost:8000
BEACON_VIEWER_API_KEY=dev-viewer-key
BEACON_AUDITOR_API_KEY=dev-auditor-key
BEACON_ADMIN_API_KEY=dev-admin-key

# Feature flags — read server-side, injected via /api/beacon/config
BEACON_AI_ENABLED=false
BEACON_STREAM_ENABLED=false

# Safe for client (no secrets)
NEXT_PUBLIC_APP_ENV=development
```

**Quickstart section (README):**

```
1. cp .env.example .env && cp frontend/.env.example frontend/.env
2. docker compose up                    # core-only (no AI)
3. open http://localhost:3000
4. Create a project → run a scan → confirm issues render
5. (optional) BEACON_AI_ENABLED=true docker compose --profile ai up
```

**Troubleshooting table:**

| Symptom                 | Likely cause                     | Fix                                             |
| ----------------------- | -------------------------------- | ----------------------------------------------- |
| Port 3000 conflict      | Node legacy running              | Use `--profile legacy` flag, Node moves to 3001 |
| 401 on all API calls    | API key mismatch in frontend env | Check `BEACON_AUDITOR_API_KEY` matches backend  |
| Fix suggestions missing | `BEACON_AI_ENABLED=false`        | Expected. Enable AI profile to test suggestions |
| Scan stuck at `running` | Playwright not installed         | `playwright install chromium` inside container  |
| ChromaDB timeout        | AI profile not running           | Start with `--profile ai` or disable AI         |
| 403 on scan create      | Using viewer key for write op    | Use `BEACON_AUDITOR_API_KEY` for scan creation  |

### Exit Criteria

- New developer runs full AI-off dashboard flow from clean machine in ≤10 minutes.
- AI-on flow documented with clear prerequisite (ChromaDB + Featherless key).

---

## Phase 1 — Contract Lock and Type Safety

**Day 1 | Blocker for Phase 3**

### Deliverables

- Versioned OpenAPI spec committed to repo
- Generated TypeScript types used in frontend API layer
- Normalized error envelope (both AI and non-AI paths)

### Tasks

**1. Export and version the OpenAPI spec:**

```bash
cd backend && python -m scripts.export_openapi > openapi/v1.json
git add openapi/v1.json
```

CI fails if `v1.json` is out of date with the running app.

**2. Generate TS types:**

```bash
npx openapi-typescript openapi/v1.json -o frontend/src/types/api.d.ts
```

Run as a pre-commit hook. Type drift = build failure.

**3. Normalize the error envelope:**

All errors from both AI and non-AI paths return:

```typescript
interface BeaconError {
  code: string; // machine-readable: "scan_failed", "ai_unavailable", "rate_limited"
  message: string; // human-readable
  detail?: unknown; // structured extra info
  request_id: string; // for support trace
  ai_degraded?: boolean; // true when error is AI-specific and core result is still available
}
```

The `ai_degraded` flag is critical: when the AI layer fails, the core result must still be returned with this flag set. The frontend renders the core result and shows a soft warning ("Fix suggestions unavailable") rather than an error state.

**4. Freeze dashboard route naming:**

No route renames without a version bump from this point.

### Exit Criteria

- Any backend response shape change fails type checks before merge.
- `ai_degraded` error path tested and renders correctly in UI.

---

## Phase 1.5 — API Versioning

**Day 1 | Required before Phase 3**

### Route structure

```
/v1/api/projects/
/v1/api/scans/
/v1/audit              # core audit, always available
/v1/audit/stream       # SSE stream, gated by BEACON_STREAM_ENABLED
/v1/rag                # AI only — returns 503 with ai_degraded:true when disabled
/v1/config             # returns feature flags safe to expose to the frontend
```

### AI-layer routes return 503 when disabled

```python
# In FastAPI router
@router.post("/v1/rag")
async def rag_query(settings: Settings = Depends(get_settings)):
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=503,
            detail={"code": "ai_disabled", "ai_degraded": True,
                    "message": "AI layer is not enabled in this environment."}
        )
    ...
```

The frontend BFF catches 503 with `ai_degraded: true` and converts it to a soft no-op, not a user-facing error.

### Legacy alias policy

Existing unversioned routes (`/api/projects/`, `/audit`, `/rag`) remain active during migration window with these response headers:

```
Deprecation: true
Sunset: 2026-06-01
X-API-Version: v1
```

Remove legacy aliases after migration window closes.

### Exit Criteria

- All new frontend code targets `/v1/` routes exclusively.
- `/v1/rag` and `/v1/audit/stream` return correct 503 with structured body when their flags are off.

---

## Phase 2 — Secure BFF Layer

**Day 1–2 | Security-critical**

### Deliverables

- Next.js route handlers at `frontend/src/app/api/beacon/*`
- All API keys server-side only — never in client bundle
- Config endpoint exposes safe feature flags to client
- Correlation ID injected per request

### BFF route map

```
/api/beacon/config             → GET /v1/config           (no auth, safe flags only)
/api/beacon/v1/projects        → FastAPI /v1/api/projects/
/api/beacon/v1/scans           → FastAPI /v1/api/scans/
/api/beacon/v1/audit           → FastAPI /v1/audit
/api/beacon/v1/audit/stream    → FastAPI /v1/audit/stream  (proxied SSE)
/api/beacon/v1/rag             → FastAPI /v1/rag           (AI only, 503 handled)
```

### `/api/beacon/config` — the AI mode gate for the frontend

```typescript
// frontend/src/app/api/beacon/config/route.ts
export async function GET() {
  return Response.json({
    aiEnabled: process.env.BEACON_AI_ENABLED === "true",
    streamEnabled: process.env.BEACON_STREAM_ENABLED === "true",
    apiVersion: "v1",
  });
}
```

The client fetches this once on boot and stores it in React context. All AI-conditional rendering reads from this context — no direct env access in client code.

### AI-layer BFF handler pattern

```typescript
// frontend/src/app/api/beacon/v1/rag/route.ts
export async function POST(req: Request) {
  const config = getServerConfig(); // reads BEACON_AI_ENABLED server-side
  if (!config.aiEnabled) {
    return Response.json(
      { code: "ai_disabled", ai_degraded: true, message: "AI layer disabled." },
      { status: 503 },
    );
  }
  return forwardToFastAPI("/v1/rag", req, { role: "auditor" });
}
```

### Correlation ID propagation

```typescript
// Injected in every BFF handler
const requestId = req.headers.get("x-request-id") ?? crypto.randomUUID();
// Forward to FastAPI: X-Request-ID: <requestId>
// Return to client: X-Request-ID: <requestId>
// Include in every error response body: { request_id: requestId }
```

### Key security rules

- `BEACON_*_API_KEY` variables: never prefixed with `NEXT_PUBLIC_`. Server-side only.
- `NEXT_PUBLIC_APP_ENV`: the only public variable. Contains no secrets.
- Auth keys injected by BFF into `Authorization` header on every FastAPI call.
- Client bundle audit (CI): grep for `BEACON_API_KEY` in compiled output fails the build.

### Exit Criteria

- No API keys appear in browser network tab under any condition.
- `/api/beacon/config` returns correct `aiEnabled` flag per env.
- All dashboard CRUD and scan actions work with backend auth enabled.

---

## Phase 3 — Endpoint Wiring

**Day 2 | Core deliverable**

### Full endpoint map

| UI action       | BFF route                                              | FastAPI route                            | Auth role | AI required |
| --------------- | ------------------------------------------------------ | ---------------------------------------- | --------- | ----------- |
| List projects   | GET `/api/beacon/v1/projects`                          | GET `/v1/api/projects/`                  | viewer    | No          |
| Create project  | POST `/api/beacon/v1/projects`                         | POST `/v1/api/projects/`                 | auditor   | No          |
| Get project     | GET `/api/beacon/v1/projects/:pid`                     | GET `/v1/api/projects/{pid}`             | viewer    | No          |
| Delete project  | DELETE `/api/beacon/v1/projects/:pid`                  | DELETE `/v1/api/projects/{pid}`          | auditor   | No          |
| Start scan      | POST `/api/beacon/v1/scans`                            | POST `/v1/api/scans/`                    | auditor   | No          |
| List scans      | GET `/api/beacon/v1/projects/:pid/scans`               | GET `/v1/api/scans/{pid}`                | viewer    | No          |
| Scan progress   | GET `/api/beacon/v1/projects/:pid/scans/:sid/progress` | GET `/v1/api/scans/{pid}/{sid}/progress` | viewer    | No          |
| Core audit      | POST `/api/beacon/v1/audit`                            | POST `/v1/audit`                         | auditor   | No          |
| Audit stream    | POST `/api/beacon/v1/audit/stream`                     | POST `/v1/audit/stream`                  | auditor   | No (gated)  |
| Fix suggestions | POST `/api/beacon/v1/rag`                              | POST `/v1/rag`                           | auditor   | **Yes**     |

### Fix suggestion rendering rules

```typescript
// IssueCard component
function IssueCard({ issue, fixSuggestion }) {
  const { aiEnabled } = useBeaconConfig();

  return (
    <div>
      <IssueDetails issue={issue} />
      {aiEnabled && fixSuggestion && (
        <FixSuggestion suggestion={fixSuggestion} />
      )}
      {aiEnabled && !fixSuggestion && (
        <span className="text-muted">Fix suggestion unavailable</span>
      )}
      {/* When aiEnabled is false: render nothing — no placeholder, no spinner */}
    </div>
  );
}
```

**Rule:** the absence of AI content must never leave an empty box, a broken layout, or a hanging loader. Either the content is there, or the space collapses cleanly.

### Persistence Strategy for AI Results

Fix suggestions must be stored in the database, linked to `scan_id` and `issue_id`. Never recompute them on refresh.

**Schema (add to your existing scans/issues tables):**

```sql
-- Linked to existing issues table
CREATE TABLE ai_fix_suggestions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id     UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  issue_id    TEXT NOT NULL,           -- axe rule id + element fingerprint
  suggestion  TEXT NOT NULL,           -- LLM-generated fix text
  model       TEXT NOT NULL,           -- e.g. "Qwen2.5-Coder-32B-Instruct"
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (scan_id, issue_id)           -- one suggestion per issue per scan
);

-- Required: without this, fetching all suggestions for a scan is a full table scan
CREATE INDEX idx_ai_fix_suggestions_scan_id ON ai_fix_suggestions(scan_id);
```

**Rules:**

- When the AI enrichment job runs, it writes suggestions to this table on completion
- The `/progress` and scan detail endpoints JOIN this table before returning — no separate AI fetch needed
- On page refresh, suggestions are read from DB instantly — no LLM call fired
- If a suggestion already exists for `(scan_id, issue_id)`, skip the LLM call entirely (idempotent)
- Suggestions are immutable after creation — never overwrite, never regenerate unless explicitly requested

### Exit Criteria

- Every UI action resolves against one stable FastAPI path.
- Issue cards render correctly with and without fix suggestions.
- AI-disabled mode shows zero broken UI states.

---

## Phase 3.5 — Streaming Resilience

**Day 2 | Required before Phase 4 e2e tests**

This phase only applies when `BEACON_STREAM_ENABLED=true`. When disabled, the UI skips streaming entirely and uses polling from Phase 3.

### Stream client behavior

```
Connect to /api/beacon/v1/audit/stream
  ├── Success → parse SSE events (started, fetching, engines_running, scoring, complete)
  ├── Disconnect → exponential backoff: 1s → 2s → 5s → 10s → give up
  │     └── On give up: fall back to polling /progress endpoint
  └── Error event → preserve last known progress snapshot, show soft warning
```

### Fallback rule

When stream falls back to polling:

- UI state is preserved (no spinner reset, no progress loss)
- User sees: "Live updates paused — checking for progress..."
- Poll interval: 3 seconds, max 20 attempts before "scan may have stalled" message
- Cancel button: stops both stream and poll loop, does not cancel the backend scan

### AI stream events

When AI is enabled, the stream may include enrichment events after `scoring`:

```
{ "event": "ai_enriching", "data": { "issues_enriched": 4, "total": 12 } }
{ "event": "ai_complete",  "data": { "suggestions_generated": 4 } }
{ "event": "ai_skipped",   "data": { "reason": "cost_firewall" } }  // silent no-op in UI
```

When AI is disabled, these events are never emitted — no dead event handlers.

### Exit Criteria

- Stream disconnect does not lose scan state.
- Fallback to polling is invisible to the user except for the soft warning.
- With `BEACON_STREAM_ENABLED=false`, stream code path is never invoked.

---

## Phase 4 — Validation Matrix

**Day 2–3 | Gate before release**

Run in this order. Each gate must be green before the next runs.

### Gate 1: Frontend static

```bash
cd frontend && npm run lint
cd frontend && npm run type-check     # catches contract drift
cd frontend && npm run build
grep -r "BEACON_.*API_KEY" .next/ && exit 1 || true   # secret leak check
```

### Gate 2: Python critical regression

```bash
python -m pytest \
  tests/unit/services/test_audit_runner_critical_bug.py \
  tests/unit/services/test_browser_prober_max_exploration.py \
  tests/unit/audit/test_site_aggregator.py \
  -q
```

### Gate 3: API smoke (both modes)

**Core-only mode (`BEACON_AI_ENABLED=false`):**

```
GET  /health                          → 200, status: ok
GET  /v1/api/projects/                → 200, array
POST /v1/api/projects/                → 201, project object
POST /v1/api/scans/                   → 202, scan started
GET  /v1/api/scans/:pid/:sid/progress → 200, progress object
POST /v1/rag                          → 503, ai_degraded: true
GET  /v1/audit (auth missing)         → 401
GET  /v1/api/projects/ (wrong key)    → 403
```

**AI-enabled mode (`BEACON_AI_ENABLED=true`):**

```
POST /v1/rag                          → 200, suggestions array
POST /v1/audit (with ai=true)         → 200, includes fix_suggestions field
```

### Gate 4: End-to-end (Playwright)

Run twice: once with `BEACON_AI_ENABLED=false`, once with `BEACON_AI_ENABLED=true`.

```
Core-only run:
  ✓ Create project
  ✓ Start scan → poll to completed
  ✓ Issues list renders (score, WCAG level, element)
  ✓ No fix suggestion UI elements visible
  ✓ No broken layouts, no hanging loaders
  ✓ Delete project

AI-enabled run:
  ✓ Create project
  ✓ Start scan → stream → completed (simulate disconnect mid-stream → fallback to poll)
  ✓ Issues list renders with fix suggestions on ≥1 issue
  ✓ Issues without suggestions degrade cleanly
  ✓ Delete project
```

### Required new tests

| Test                                                   | Location                            | Covers               |
| ------------------------------------------------------ | ----------------------------------- | -------------------- |
| BFF config returns correct `aiEnabled` per env         | `tests/bff/test_config.ts`          | AI mode gate         |
| `ai_degraded: true` renders as soft warning, not error | `tests/ui/test_issue_card.tsx`      | Graceful degradation |
| 401/403 → user-safe error message (not raw JSON)       | `tests/bff/test_auth_errors.ts`     | Auth UX              |
| Poll timeout → "scan may have stalled" message         | `tests/ui/test_scan_poll.tsx`       | No infinite spinner  |
| Stream disconnect → fallback to poll, state preserved  | `tests/e2e/test_stream_fallback.ts` | Stream resilience    |
| OpenAPI spec drift → type-check fails                  | CI pre-commit hook                  | Contract safety      |
| No `BEACON_*KEY` in compiled bundle                    | CI grep gate                        | Secret isolation     |

### Exit Criteria

- All gates green in CI.
- Both AI-off and AI-on e2e suites pass.
- Zero uncaught promise errors or broken layouts in browser console during golden flows.

---

## Phase 4.5 — Caching Layer

**Day 3 | Optional but high ROI**

You do not need a complex cache. Even a basic Redis setup eliminates redundant DB reads for the most-fetched data. Start small.

### What to cache

| Data                                      | Cache key                    | TTL        | Invalidation trigger              |
| ----------------------------------------- | ---------------------------- | ---------- | --------------------------------- |
| Project list (per user/key)               | `projects:{key_label}`       | 60s        | Any project create/delete         |
| Scan result (immutable after `completed`) | `scan:{scan_id}:result`      | indefinite | Never — scans don't change        |
| AI fix suggestions (per scan)             | `scan:{scan_id}:suggestions` | indefinite | Never — suggestions are immutable |
| `/v1/config` feature flags                | `config:global`              | 300s       | On env change / deploy            |

**Scan results and AI suggestions are immutable after completion — cache them indefinitely.** There is no correctness risk, only a cache-clear-on-deploy question (which is fine).

### Implementation (simple Python pattern)

```python
import json
import redis

r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

async def get_scan_result(scan_id: str):
    cached = r.get(f"scan:{scan_id}:result")
    if cached:
        return json.loads(cached)
    result = await db.fetch_scan(scan_id)
    if result["status"] == "completed":
        r.set(f"scan:{scan_id}:result", json.dumps(result))  # no TTL — immutable
    return result
```

### Docker Compose addition

```yaml
redis:
  image: redis:7-alpine
  ports: ["6379:6379"]
  # No profiles — Redis is cheap enough to always run locally
```

**Env variable:** `REDIS_URL=redis://localhost:6379`

### Build order recommendation

- **Now:** Add Redis to Docker Compose, cache scan results and AI suggestions only (immutable = safe, zero invalidation logic needed)
- **Later:** Add project list cache with 60s TTL when you have multiple users hammering the list endpoint
- **Never (yet):** Don't build a sophisticated cache invalidation system. The complexity isn't worth it at your current scale.

---

## Phase 4.6 — Database Schema Versioning

**Day 3 | Before release | Non-negotiable**

API versioning is already covered. DB schema versioning is equally important and is missing from the current setup.

### Use Alembic

```bash
pip install alembic
alembic init alembic
```

**`alembic/env.py`** — point at your SQLAlchemy `Base.metadata` and database URL from env.

### Migration naming convention (tied to API version)

```
alembic/versions/
  0001_v1_initial_schema.py
  0002_v1_add_ai_fix_suggestions.py
  0003_v1_add_scan_timeout_field.py
```

Prefix with the API version the migration corresponds to. When you bump to v2, new migrations are prefixed `0004_v2_...`.

### CI gate

```bash
# In CI, before running tests:
alembic upgrade head

# Check for unapplied migrations (fails CI if a migration was added without running it)
alembic check
```

### Rules

- Every DB change ships with a migration file — no manual `ALTER TABLE` in production
- Migrations run automatically on deploy (`alembic upgrade head` in the deploy script), before the app starts
- Rollback migration (`alembic downgrade -1`) is written and tested for every migration that changes column types or drops data
- The `ai_fix_suggestions` table from Phase 3 requires its own migration file: `0002_v1_add_ai_fix_suggestions.py`

---

## Phase 5 — Observability

### Correlation IDs

- Generated at BFF if absent: `X-Request-ID: <uuid>`
- Forwarded to FastAPI on every call
- Included in every log line and every error response body
- When AI layer is called: same request ID forwarded to LLM/RAG calls for end-to-end trace

### Structured log fields (every request)

```json
{
  "request_id": "...",
  "project_id": "...",
  "scan_id": "...",
  "endpoint": "/v1/api/scans/",
  "method": "POST",
  "status": 202,
  "latency_ms": 143,
  "ai_enabled": false,
  "ai_fired": false,
  "key_label": "auditor-dev",
  "role": "auditor"
}
```

### Runtime monitors

| Metric                          | Alert threshold                        |
| ------------------------------- | -------------------------------------- |
| 5xx rate by endpoint            | > 1% over 5 min                        |
| Scan failure ratio              | > 5%                                   |
| Scan timeout ratio              | > 2%                                   |
| AI layer 503 rate               | > 10% when AI enabled                  |
| LLM call rate                   | > 15% of issues (cost firewall breach) |
| Stream disconnect rate          | > 20%                                  |
| Stream fallback-to-poll rate    | > 30%                                  |
| p95 latency: project list       | > 800ms                                |
| p95 latency: scan progress poll | > 400ms                                |

### AI cost firewall logging

When the cost firewall suppresses an LLM call, log:

```json
{
  "event": "ai_skipped",
  "reason": "cost_firewall",
  "issue_id": "...",
  "scan_id": "..."
}
```

Aggregate this daily. If suppression rate > 85%, the firewall threshold needs recalibration.

---

## Phase 5.5 — Abuse Controls

**Day 3 | Before full release**

### Rate limits (per API key)

| Endpoint class                                         | Limit       |
| ------------------------------------------------------ | ----------- |
| Read endpoints (`/projects/`, `/scans/`, `/progress/`) | 300 req/min |
| Scan creation                                          | 10 req/min  |
| Audit endpoints                                        | 5 req/min   |
| RAG/AI endpoints                                       | 20 req/min  |

### Scan quotas (per plan tier — INR pricing aligned)

| Tier              | Daily scans | Monthly scans | Concurrent scans |
| ----------------- | ----------- | ------------- | ---------------- |
| Free              | 5           | 50            | 1                |
| Starter (₹999/mo) | 50          | 500           | 2                |
| Pro (₹4,999/mo)   | 200         | 2,000         | 5                |
| Enterprise        | Unlimited   | Unlimited     | 20               |

### Quota exceeded response

```json
{
  "code": "quota_exceeded",
  "message": "Daily scan limit reached. Resets at 00:00 IST.",
  "retry_after": 14400,
  "upgrade_url": "/pricing"
}
```

Frontend shows: "You've used all scans for today. Resets in 4 hours." with upgrade CTA if on Free tier.

### Global safety caps

- Max concurrent scans per workspace: `BEACON_MAX_CONCURRENT_SCANS` (default: 10)
- Global cap across all tenants: `BEACON_GLOBAL_SCAN_CAP` (default: 50)
- AI calls per scan: capped at `ceil(issue_count * 0.15)` by cost firewall

---

## Phase 6 — Release

**Day 3**

### Rollout order (never skip steps)

1. Deploy backend to staging.
2. Run Gate 1 + Gate 3 smoke suite against staging.
3. Deploy frontend/BFF to staging.
4. Run full Gate 4 e2e suite against staging (both AI modes).
5. Verify `/api/beacon/config` returns correct flags in staging env.
6. Canary: 10% of production traffic for 2 hours.
7. Monitor Phase 5 dashboards during canary window.
8. Full release after 2 hours of stable telemetry.

### Rollback triggers

Any of the following → immediate rollback:

- 5xx rate > 2% sustained for 3 minutes
- Scan failure ratio > 10%
- AI layer 503 rate > 50% when `BEACON_AI_ENABLED=true` in production
- Any secret visible in browser network tab (immediate, no grace period)

### Rollback steps

1. Revert frontend to previous image.
2. Revert backend to `wireup-baseline` tag.
3. Run Gate 3 smoke suite to confirm rollback stable.
4. Post incident summary before re-attempting release.

---

## High-Risk Areas

| Risk                             | Severity | Mitigation                                       |
| -------------------------------- | -------- | ------------------------------------------------ |
| Auth key in client bundle        | Critical | CI grep gate, BFF-only key pattern               |
| AI layer blocks core scan result | High     | `ai_degraded` flag, AI always async/non-blocking |
| Node port conflict with Next     | High     | Node on 3001, Docker profiles                    |
| ChromaDB timeout under load      | High     | AI calls fire async after core result returned   |
| Contract drift after release     | Medium   | OpenAPI type generation in CI                    |
| Poll hang from stale scan        | Medium   | 20-attempt max, "scan may have stalled" UX       |
| LLM cost overrun                 | Medium   | 15% issue cap, cost firewall metrics alert       |
| Stream instability               | Medium   | Bounded retry, automatic poll fallback           |

---

## ⚠️ Scope Honesty — You Are One Developer

This plan is complete and correct. It is also large. Before you start building, be honest about what matters right now versus what can wait.

**The trap:** designing for thousands of users when you have zero paying ones. Every hour spent on Celery, sophisticated cache invalidation, or multi-region rollout is an hour not spent on the thing that actually determines whether BEACON survives: getting real users and validating the product.

### What you must build now (blocks launch)

- Phase 0 through Phase 3 — baseline, ergonomics, contract, BFF wiring, endpoint map
- `FastAPI BackgroundTasks` for async scans (not Celery)
- `ai_fix_suggestions` table + Alembic migration
- Redis with immutable scan/suggestion caching only
- Phase 4 validation gates (both AI modes)

### What to build only when you have users

- RQ or Celery (when you have >1 concurrent user regularly)
- Project list caching with TTL invalidation (when list endpoint is slow under real load)
- Phase 5.5 abuse controls and quota tiers (when you have paying users to protect)
- Stream resilience (Phase 3.5) — only if streaming is in active use, not just implemented

### What to defer indefinitely until real evidence

- Multi-region deployment
- Priority queues
- Sophisticated cache invalidation logic
- Full observability stack with custom dashboards

**The right order is:** working product → first user → first paying user → scale the parts that are actually breaking.

A plan that ships is worth more than a plan that is perfect.

---

## Definition of Done

- [ ] `docker compose up` runs full dashboard flow with no manual steps
- [ ] `docker compose --profile ai up` enables AI features cleanly
- [ ] All Phase 4 gates green in CI for both AI-off and AI-on modes
- [ ] No API keys in browser network tab (verified by CI grep + manual check)
- [ ] `/api/beacon/config` correctly gates AI feature rendering
- [ ] Issue cards render without fix suggestions in AI-off mode — zero broken layouts
- [ ] Stream fallback to polling works and preserves UI state
- [ ] Correlation IDs present in all log lines and error responses
- [ ] Scans execute via background worker — API thread never blocked
- [ ] AI enrichment runs as post-scan async job — core result available before suggestions
- [ ] `ai_fix_suggestions` table exists with Alembic migration applied
- [ ] Fix suggestions read from DB on refresh — no LLM recomputation
- [ ] Redis running; immutable scan results and suggestions are cached
- [ ] `alembic upgrade head` runs cleanly in CI before tests
- [ ] Phase 5 monitors active in staging before canary
- [ ] Rollback playbook tested once in staging
- [ ] README quickstart verified on a clean machine

---

## Immediate Next Actions (in order)

1. **Decide Node disposition today.** Pick port 3001 legacy or sunset. This blocks Phase 3.
2. **Verify `/v1/audit/stream` exists and is stable** before scheduling Phase 3.5 work. If it doesn't exist yet, descope streaming from this wiring sprint and add a polling-only path.
3. **Add `BEACON_AI_ENABLED` flag to FastAPI settings** and gate `/v1/rag` behind it with the correct 503 shape.
4. **Add `/v1/config` endpoint** returning AI + stream flags — this is what the BFF config route reads.
5. **Run baseline smoke in both AI modes** and commit results. Don't start Phase 1 until both pass.
