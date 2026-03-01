# Test Coverage Analysis — Colorado Care Assist Platform

**Date:** 2026-03-01
**Analyst:** Claude Code

---

## Executive Summary

The codebase has **46 Python test files** and **6 TypeScript spec files**, but suffers from fundamental infrastructure gaps: no unified test runner, no coverage reporting, no mocking/fixture framework, and most tests are standalone scripts requiring manual execution with live credentials. The result is that critical business logic — authentication, memory decay, tool execution, shift management — has **no isolated unit tests**.

**Overall Test Quality: 4/10**

---

## Current State

### What Exists

| Area | Test Files | Style | Quality |
|------|-----------|-------|---------|
| Portal routes | `tests/test_routes.py` (4 tests) | unittest + TestClient | Smoke-test only (checks status codes) |
| Import/structure | `tests/test_connectivity.py` (2 tests) | unittest | Trivial — verifies imports |
| Gigi voice/WellSky | 15 files in `gigi/` (60,000+ lines) | Standalone scripts | Integration-heavy, requires live APIs |
| Recruiting | `recruiting/test_app.py`, `test_db.py` | Manual scripts | Not unittest/pytest — uses print() |
| Sales frontend | 6 `.spec.ts` files | Vitest | Proper unit tests, but limited scope |
| Sales backend | 10 files (9 archived) | Standalone scripts | Mostly dead/archived |
| Root-level | 10 scattered test files | Mixed | Ad-hoc, manual execution |
| Legacy | 6 files in `legacy_tests/` | Various | Abandoned |

### What's Missing

- **No `pytest.ini` or `pyproject.toml`** — no unified test runner configuration
- **No `conftest.py`** — no shared fixtures, no database mocking
- **No `pytest`, `pytest-cov`, `pytest-asyncio`** in dependencies
- **No coverage reporting** — no way to measure what's tested
- **No CI/CD for Python tests** — GitHub Actions only runs frontend Vitest + ESLint
- **No mocking layer** — all tests hit real APIs or databases
- **No test database** — tests either skip DB or use production

---

## Gap Analysis by Component

### 1. Authentication & Authorization (CRITICAL — 0% unit coverage)

**Files:** `services/auth_service.py` (312 lines)

This is a security-critical component with **zero isolated tests**. It handles:

- Google OAuth flow (authorization URL generation, callback handling, token exchange)
- Session token creation and verification (via `itsdangerous`)
- Domain-based access control (`allowed_domains`)
- Portal proxy authentication (`X-Portal-Secret` header validation)
- CSRF protection (OAuth state validation)
- Demo bypass guard (`DEMO_BYPASS` only in dev environment)

**What should be tested:**
- `verify_session()` with valid/expired/tampered tokens
- `get_current_user()` with bearer token, cookie, portal headers, and missing auth
- Domain validation (allowed vs blocked domains)
- CSRF state mismatch rejection
- Demo bypass only activates in development environment
- Edge cases: empty email, missing `@`, malformed headers

**Priority: HIGH** — authentication bugs are security vulnerabilities.

---

### 2. Gigi Memory System (HIGH — 0% unit coverage)

**File:** `gigi/memory_system.py` (589 lines)

Core AI memory with confidence scoring, decay, and conflict detection — completely untested in isolation.

**What should be tested:**
- `create_memory()` — confidence clamping per memory type (e.g., CORRECTION max 0.9)
- `decay_memories()` — decay rates by type, inactive thresholds, temporary memory expiry
- `reinforce_memory()` — confidence boost with cap
- `_might_conflict()` — opposite-word detection logic
- `query_memories()` — filtering by category, status, confidence, type
- Edge cases: legacy `FACT` type handling, malformed enum values in DB

**Priority: HIGH** — memory decay bugs silently corrupt Gigi's knowledge base.

---

### 3. Gigi Failure Handler (HIGH — 0% unit coverage)

**File:** `gigi/failure_handler.py` (587 lines)

The failure protocol system has complex stateful logic for meltdown detection that is completely untested.

**What should be tested:**
- `detect_meltdown()` — 3 failures in 5 minutes triggers meltdown
- `log_failure()` — meltdown upgrade logic (severity/action escalation)
- `handle_tool_failure()` — critical vs non-critical tool classification
- `handle_low_confidence()` — action selection by confidence bracket (<0.3, <0.6, >=0.6)
- `safe_tool_call()` — wrapper success/failure paths
- Edge cases: DB connection failure during meltdown detection (fallback to in-memory)

**Priority: HIGH** — failure handling bugs cascade into production outages.

---

### 4. Tool Executor (HIGH — 0% unit coverage)

**File:** `gigi/tool_executor.py` (2,009 lines)

The shared tool execution engine for all Gigi channels routes 90+ tool calls. No isolated tests exist.

**What should be tested:**
- Each tool dispatch branch (at minimum, verify correct function is called)
- Error handling for unknown tool names
- Database connection pool management (`_get_db_pool`, `_get_conn`, `_put_conn`)
- Tool input validation (missing required fields, wrong types)
- Graceful degradation when external services are unavailable

**Priority: HIGH** — a bug here breaks all Gigi channels simultaneously.

---

### 5. Tool Registry & Channel Filtering (MEDIUM — 0% unit coverage)

**File:** `gigi/tool_registry.py` (182 lines)

**What should be tested:**
- `get_tools("sms")` returns exactly 43 tools (excludes 47)
- `get_tools("voice")` returns exactly 86 tools from registry
- `get_tools("telegram")` returns all 90 tools
- No duplicate tool names in `CANONICAL_TOOLS`
- Every tool name in registry has a matching handler in `tool_executor.py`

**Priority: MEDIUM** — misfiltered tools cause channel-specific failures.

---

### 6. Portal Routes (MEDIUM — ~5% coverage)

**File:** `portal/portal_app.py` (12,300 lines)

Only 4 basic smoke tests exist (`test_routes.py`). The portal has 26+ tiles with complex routes.

**What should be tested:**
- All authenticated routes return 401 without auth
- Route-specific logic (payroll conversion, fax handling, WellSky data display)
- File upload endpoints (payroll CSV, face sheet scanner)
- API endpoints (`/api/*` routes)
- Error handling for missing database or external service

**Priority: MEDIUM** — large surface area with minimal coverage.

---

### 7. WellSky Service (MEDIUM — integration tests only)

**File:** `services/wellsky_service.py` (6,500 lines)

Existing tests (`test_wellsky_integration.py` at 20,475 lines) are all live API tests. No mocked unit tests.

**What should be tested (with mocks):**
- FHIR API response parsing (Patient, Practitioner, Appointment resources)
- Error handling for API timeouts, rate limits, auth failures
- Token refresh logic
- Cache invalidation
- Data transformation (FHIR → internal models)

**Priority: MEDIUM** — existing integration tests provide coverage, but they can't run in CI.

---

### 8. Sales-WellSky Sync (MEDIUM — 0% unit coverage)

**File:** `services/sales_wellsky_sync.py` (512 lines)

Lifecycle sync between Sales Dashboard and WellSky — untested.

**What should be tested:**
- Stage-to-status mapping (e.g., "Closed Won" → "Ready to Schedule" → isClient=true)
- `sync_deal_to_prospect()` — creates WellSky prospect on deal creation
- `sync_deal_stage_change()` — updates WellSky status on stage transition
- Background thread error isolation (errors logged, never surface to caller)

**Priority: MEDIUM** — sync bugs cause data inconsistency between systems.

---

### 9. Fax Service (MEDIUM — 0% unit coverage)

**File:** `services/fax_service.py` (981 lines)

RingCentral fax send/receive with multi-file handling — untested.

**What should be tested:**
- Fax send with single/multiple attachments
- Cover page generation
- Inbound fax polling and notification
- Error handling for large files, unsupported formats

---

### 10. Gigi Subsystems (LOW-MEDIUM — 0% unit coverage each)

| Subsystem | File | Lines | Key Logic to Test |
|-----------|------|-------|-------------------|
| Conversation Store | `conversation_store.py` | 405 | CRUD, per-channel isolation, cleanup |
| Mode Detector | `mode_detector.py` | 539 | Time-based mode selection, 8 modes |
| Pattern Detector | `pattern_detector.py` | 274 | Failure pattern detection, trends |
| Self Monitor | `self_monitor.py` | 313 | Weekly audit aggregation |
| Clock Reminders | `clock_reminder_service.py` | 342 | Business hours logic, SMS deduplication |
| Daily Confirmations | `daily_confirmation_service.py` | 226 | Shift matching, message formatting |
| Knowledge Graph | `knowledge_graph.py` | 399 | Entity/relation CRUD, graph traversal |
| Sequential Thinking | `sequential_thinking.py` | 243 | Chain management, revision, expiry |
| Learning Pipeline | `learning_pipeline.py` | 1,829 | Scoring logic, evaluation aggregation |
| Simulation Service | `simulation_service.py` | 688 | WebSocket tool capture, scoring |

---

### 11. Voice Brain & Channel Handlers (LOW — integration tests exist)

**Files:** `voice_brain.py` (1,755), `telegram_bot.py` (2,492), `ringcentral_bot.py` (4,618)

The 22-scenario voice simulation suite (`scripts/run_gigi_simulations.py`) provides good integration coverage. However, unit tests for:
- WebSocket ping/pong handling
- `_detect_semantic_loop()` in RC bot (cosine similarity > 0.85)
- Response task cancellation on new `response_required`
- System prompt construction (`_build_*_system_prompt()`)

---

### 12. Recruiting Dashboard (LOW — trivial tests only)

**Files:** `recruiting/app.py` (4,628 lines), `recruiting/test_app.py` (166 lines)

Tests are manual scripts using `print()`, not unittest assertions. Cover only import and basic DB create/delete.

---

### 13. Sales Backend (LOW — mostly archived)

**File:** `sales/app.py` (11,748 lines)

9 of 10 test files are archived. Only `test_business_lookup.py` remains active.

---

## Recommended Improvements (Prioritized)

### Phase 1: Foundation (Week 1)

**Goal:** Establish test infrastructure so all future tests have a home.

1. **Add pytest + plugins to requirements**
   ```
   pytest>=8.0
   pytest-asyncio>=0.23
   pytest-cov>=5.0
   pytest-mock>=3.14
   httpx  # already present, needed for async test client
   ```

2. **Create `pyproject.toml` with test configuration**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   asyncio_mode = "auto"
   ```

3. **Create `tests/conftest.py` with shared fixtures**
   - Mock database connection (use SQLite in-memory or `psycopg2` mock)
   - Mock external APIs (WellSky, RingCentral, Google, Retell)
   - FastAPI TestClient fixture with authentication bypass
   - Environment variable fixtures

4. **Add Python test step to `.github/workflows/check.yml`**
   ```yaml
   - name: Run Python tests
     run: pytest tests/ --cov=. --cov-report=xml -x
   ```

### Phase 2: Security-Critical Tests (Week 2)

5. **Auth service unit tests** (`tests/test_auth_service.py`)
   - Session token creation/verification/expiry
   - Domain validation
   - CSRF state validation
   - Portal proxy header authentication
   - Demo bypass environment guard

6. **Memory system unit tests** (`tests/test_memory_system.py`)
   - Confidence clamping per type
   - Decay rate calculations
   - Conflict detection
   - Reinforcement with caps

7. **Failure handler unit tests** (`tests/test_failure_handler.py`)
   - Meltdown detection threshold
   - Severity classification
   - Action selection logic

### Phase 3: Core Business Logic (Weeks 3-4)

8. **Tool registry tests** (`tests/test_tool_registry.py`)
   - Channel filtering correctness
   - No duplicate tool names
   - Tool name ↔ executor mapping

9. **Tool executor tests** (`tests/test_tool_executor.py`)
   - Dispatch routing for each tool
   - Error handling for unknown tools
   - Connection pool lifecycle

10. **Sales-WellSky sync tests** (`tests/test_sales_wellsky_sync.py`)
    - Stage → status mapping
    - Background thread error isolation

11. **Portal route tests** (`tests/test_portal_routes.py`)
    - Expand from 4 to cover all major routes
    - Auth-required routes return 401
    - File upload validation

### Phase 4: Subsystem Tests (Weeks 5-6)

12. **Mode detector tests** — time-based mode selection logic
13. **Pattern detector tests** — trend detection algorithms
14. **Clock reminder tests** — business hours boundaries
15. **Knowledge graph tests** — entity/relation CRUD
16. **Conversation store tests** — channel isolation, cleanup

### Phase 5: Cleanup & Maintenance

17. **Remove or restore `legacy_tests/`** — 6 abandoned files
18. **Remove or restore `sales/scripts/archive/`** — 9 archived test files
19. **Convert `recruiting/test_app.py`** to proper pytest
20. **Add coverage thresholds** — fail CI if coverage drops below baseline

---

## Quick Wins (Can Be Done Today)

These require no infrastructure changes:

1. **Tool registry validation test** — verify no duplicate names, correct channel counts
2. **Memory confidence clamping test** — pure logic, no DB needed if you mock the connection
3. **Failure handler action selection test** — `handle_low_confidence()` is pure logic
4. **Auth domain validation test** — `allowed_domains` check is pure string logic
5. **Mode detector time logic test** — time-based mode selection is deterministic

---

## Metrics to Track

| Metric | Current | Target (3 months) |
|--------|---------|-------------------|
| Python unit tests | ~10 (in unittest) | 150+ (in pytest) |
| Code coverage | Unknown (no tooling) | 40%+ for core modules |
| CI test execution | Frontend only | Frontend + Backend |
| Test execution time | Manual, unknown | < 60s for unit suite |
| Mocked vs Live tests | ~5% mocked | 80%+ mocked (unit), 20% live (integration) |
