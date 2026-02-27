# Deep Integration Test Spec

**Purpose:** Canonical test URLs for "test my sites" deep integration testing.
**Last Updated:** 2026-02-27

---

## Portal (localhost:8765)

### Health & Core

| #   | Method | URL       | Expected                         |
| --- | ------ | --------- | -------------------------------- |
| 1   | GET    | `/health` | 200, JSON `{"status":"healthy"}` |
| 2   | GET    | `/`       | 307 redirect to Google OAuth     |
| 3   | GET    | `/login`  | 307 redirect to Google OAuth     |

### API Endpoints (all require auth — expect 401 unauthenticated)

| #   | Method | URL                             | Expected                           |
| --- | ------ | ------------------------------- | ---------------------------------- |
| 4   | GET    | `/api/tools`                    | 401                                |
| 5   | GET    | `/api/activity-stream`          | 401                                |
| 6   | GET    | `/api/vouchers`                 | 401                                |
| 7   | GET    | `/api/incident-reports/latest`  | 401                                |
| 8   | GET    | `/api/monitoring-visits/latest` | 401                                |
| 9   | GET    | `/api/internal/wellsky/shifts`  | 401                                |
| 10  | GET    | `/api/weather`                  | 400 (requires query params) or 401 |
| 11  | GET    | `/api/wellsky/status`           | 401                                |

### Gigi Learning/Evaluation API (require auth)

| #   | Method | URL                                      | Expected |
| --- | ------ | ---------------------------------------- | -------- |
| 12  | GET    | `/api/gigi/learning/evaluations?limit=5` | 401      |
| 13  | GET    | `/api/gigi/learning/stats`               | 401      |
| 14  | GET    | `/api/gigi/learning/flagged`             | 401      |

### Gigi Dashboard APIs (require auth)

| #   | Method | URL                        | Expected |
| --- | ------ | -------------------------- | -------- |
| 15  | GET    | `/api/gigi/schedule`       | 401      |
| 16  | GET    | `/api/gigi/communications` | 401      |
| 17  | GET    | `/api/gigi/issues`         | 401      |
| 18  | GET    | `/api/gigi/reports`        | 401      |

### Portal Pages (require auth)

| #   | Method | URL          | Expected |
| --- | ------ | ------------ | -------- |
| 19  | GET    | `/fax`       | 401      |
| 20  | GET    | `/marketing` | 401      |
| 21  | GET    | `/vouchers`  | 401      |

### Static Assets

| #   | Method | URL                   | Expected |
| --- | ------ | --------------------- | -------- |
| 22  | GET    | `/static/favicon.ico` | 200      |
| 23  | GET    | `/static/favicon.svg` | 200      |

### Database

| #   | Query                                   | Expected            |
| --- | --------------------------------------- | ------------------- |
| 24  | `SELECT COUNT(*) FROM portal_tools`     | > 0                 |
| 25  | `SELECT COUNT(*) FROM activity_feed`    | > 0                 |
| 26  | `SELECT COUNT(*) FROM gigi_evaluations` | >= 0 (table exists) |
| 27  | `SELECT COUNT(*) FROM vouchers`         | >= 0 (table exists) |

---

## Gigi (localhost:8767)

### Health & Core

| #   | Method | URL                | Expected                                   |
| --- | ------ | ------------------ | ------------------------------------------ |
| 28  | GET    | `/gigi/health`     | 200, JSON with status/version/memory stats |
| 29  | GET    | `/gigi/api/status` | 200, JSON status                           |
| 30  | GET    | `/gigi/shadow`     | 200, HTML dashboard                        |

### Shadow/Learning API (require gigi token)

| #   | Method | URL                              | Expected                               |
| --- | ------ | -------------------------------- | -------------------------------------- |
| 31  | GET    | `/gigi/api/gigi/learning/stats`  | 401 (no token)                         |
| 32  | POST   | `/gigi/api/gigi/learning/run`    | 401 (no token)                         |
| 33  | POST   | `/gigi/api/gigi/shadow/feedback` | 405 on GET / 401 on POST without token |

### Ask-Gigi API (require Bearer token)

| #   | Method | URL                              | Expected                                |
| --- | ------ | -------------------------------- | --------------------------------------- |
| 34  | POST   | `/gigi/api/ask-gigi` (no Bearer) | 401 `{"detail":"Missing Bearer token"}` |

### Webhook Endpoints (verify they exist and enforce auth)

| #   | Method | URL                                       | Expected                     |
| --- | ------ | ----------------------------------------- | ---------------------------- |
| 35  | POST   | `/gigi/webhook/retell` (empty body)       | 401 (signature verification) |
| 36  | POST   | `/gigi/webhook/imessage` (no password)    | 401                          |
| 37  | POST   | `/gigi/webhook/beetexting` (no auth)      | 401                          |
| 38  | POST   | `/gigi/webhook/ringcentral-sms` (no auth) | 401                          |
| 39  | POST   | `/gigi/webhook/inbound-sms`               | exists (not 404)             |

### Simulation Endpoints

| #   | Method | URL                      | Expected                     |
| --- | ------ | ------------------------ | ---------------------------- |
| 40  | POST   | `/gigi/simulate/callout` | 401 or 422 (exists, not 404) |

### Database

| #   | Query                                     | Expected            |
| --- | ----------------------------------------- | ------------------- |
| 41  | `SELECT COUNT(*) FROM gigi_conversations` | > 0                 |
| 42  | `SELECT COUNT(*) FROM gigi_memories`      | > 0                 |
| 43  | `SELECT COUNT(*) FROM gigi_kg_entities`   | > 0                 |
| 44  | `SELECT COUNT(*) FROM gigi_kg_relations`  | > 0                 |
| 45  | `SELECT COUNT(*) FROM gigi_sms_drafts`    | >= 0 (table exists) |
| 46  | `SELECT COUNT(*) FROM gigi_evaluations`   | >= 0 (table exists) |

### Evaluation Pipeline CLI

| #   | Command                                    | Expected                 |
| --- | ------------------------------------------ | ------------------------ |
| 47  | `python -m gigi.learning_pipeline --stats` | Runs, returns JSON stats |

---

## Sales (localhost:8769)

### Health & Core

| #   | Method | URL                 | Expected                      |
| --- | ------ | ------------------- | ----------------------------- |
| 48  | GET    | `/sales/health`     | 200, JSON `{"status":"ok"}`   |
| 49  | GET    | `/sales/`           | 307 redirect to `/auth/login` |
| 50  | GET    | `/sales/auth/login` | 307 redirect to Google OAuth  |

### API Endpoints (require auth — expect 401)

| #   | Method | URL                            | Expected |
| --- | ------ | ------------------------------ | -------- |
| 51  | GET    | `/sales/admin/sales`           | 401      |
| 52  | GET    | `/sales/admin/contacts`        | 401      |
| 53  | GET    | `/sales/api/dashboard/summary` | 401      |
| 54  | GET    | `/sales/api/deals`             | 401      |
| 55  | GET    | `/sales/api/contacts`          | 401      |
| 56  | GET    | `/sales/api/pipeline/stages`   | 401      |
| 57  | GET    | `/sales/api/pipeline/leads`    | 401      |

### Database

| #   | Check                                                         | Expected    |
| --- | ------------------------------------------------------------- | ----------- |
| 58  | `ls sales/sales_tracker.db`                                   | File exists |
| 59  | `sqlite3 sales/sales_tracker.db "SELECT COUNT(*) FROM deals"` | >= 0        |

---

## Recruiting (localhost:8771)

### Health & Core

| #   | Method | URL                  | Expected                    |
| --- | ------ | -------------------- | --------------------------- |
| 60  | GET    | `/recruiting/health` | 200, JSON `{"status":"ok"}` |
| 61  | GET    | `/recruiting/`       | 302 redirect to portal auth |

### API Endpoints (require auth — expect error)

| #   | Method | URL                          | Expected                                     |
| --- | ------ | ---------------------------- | -------------------------------------------- |
| 62  | GET    | `/recruiting/api/leads`      | 401 or `{"error":"Authentication required"}` |
| 63  | GET    | `/recruiting/api/applicants` | 401 or `{"error":"Authentication required"}` |
| 64  | GET    | `/recruiting/api/pipeline`   | 401 or `{"error":"Authentication required"}` |
| 65  | GET    | `/recruiting/api/stats`      | 401 or `{"error":"Authentication required"}` |

### Database

| #   | Query                       | Expected                             |
| --- | --------------------------- | ------------------------------------ |
| 66  | `SELECT COUNT(*) FROM lead` | > 0 (note: table is `lead` singular) |

---

## Standalone Sites

### Marketing Website (localhost:3000)

| #   | Method | URL                      | Expected  |
| --- | ------ | ------------------------ | --------- |
| 67  | GET    | `http://localhost:3000/` | 200, HTML |

### Hesed Home Care (localhost:3001)

| #   | Method | URL                          | Expected              |
| --- | ------ | ---------------------------- | --------------------- |
| 68  | GET    | `http://localhost:3001/test` | 301 redirect to HTTPS |

**Note:** Port 3001 forces HTTPS redirect on ALL routes in production mode (including `/test`). Use external URL or skip in local testing.

### Elite Trading MCP (localhost:3002)

| #   | Method | URL                            | Expected                         |
| --- | ------ | ------------------------------ | -------------------------------- |
| 69  | GET    | `http://localhost:3002/health` | 200, JSON `{"status":"healthy"}` |

### PowderPulse (localhost:3003)

| #   | Method | URL                            | Expected                    |
| --- | ------ | ------------------------------ | --------------------------- |
| 70  | GET    | `http://localhost:3003/`       | 200                         |
| 71  | GET    | `http://localhost:3003/health` | 200, JSON `{"status":"ok"}` |

### Weather Sniper Bot — Polymarket (localhost:3010, PAPER TRADING)

| #   | Method | URL                               | Expected                      |
| --- | ------ | --------------------------------- | ----------------------------- |
| 72  | GET    | `http://localhost:3010/health`    | 200                           |
| 73  | GET    | `http://localhost:3010/status`    | 200, JSON with running/config |
| 74  | GET    | `http://localhost:3010/forecasts` | 200, JSON with city forecasts |
| 75  | GET    | `http://localhost:3010/orders`    | 200, JSON                     |
| 76  | GET    | `http://localhost:3010/pnl`       | 200, JSON with P&L data       |

### Kalshi Weather Bot (localhost:3011, REAL MONEY)

| #   | Method | URL                            | Expected                      |
| --- | ------ | ------------------------------ | ----------------------------- |
| 77  | GET    | `http://localhost:3011/health` | 200                           |
| 78  | GET    | `http://localhost:3011/status` | 200, JSON with balance/orders |

### Status Dashboard (localhost:3012)

| #   | Method | URL                                  | Expected                           |
| --- | ------ | ------------------------------------ | ---------------------------------- |
| 79  | GET    | `http://localhost:3012/`             | 200, HTML                          |
| 80  | GET    | `http://localhost:3012/api/services` | 200, JSON with service health      |
| 81  | GET    | `http://localhost:3012/api/apis`     | 200, JSON with external API health |

### Trading Dashboard (localhost:3014)

| #   | Method | URL                            | Expected  |
| --- | ------ | ------------------------------ | --------- |
| 82  | GET    | `http://localhost:3014/`       | 200       |
| 83  | GET    | `http://localhost:3014/health` | 200, JSON |

---

## Infrastructure

### Database Overall

| #   | Query                                                                          | Expected |
| --- | ------------------------------------------------------------------------------ | -------- |
| 84  | `SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'` | >= 164   |

### Cloudflare Tunnel (external access)

| #   | Method | URL                                             | Expected |
| --- | ------ | ----------------------------------------------- | -------- |
| 85  | GET    | `https://portal.coloradocareassist.com/health`  | 200      |
| 86  | GET    | `https://coloradocareassist.com/`               | 200      |
| 87  | GET    | `https://status.coloradocareassist.com/`        | 200      |
| 88  | GET    | `https://staging.coloradocareassist.com/health` | 200      |

---

## Total: 88 tests
