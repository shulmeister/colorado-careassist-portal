# Changelog

## Feb 23, 2026
- Monitoring Visit Form: Offline PWA form at `/mv` with auto-save drafts and auto-sync
- Monitoring Visit Form: Service worker + manifest for installable mobile app
- Monitoring Visit Form: `monitoring_visits` DB table
- Monitoring Visit Form: POST /api/monitoring-visits/sync (DB + Google Drive upload to "Monitoring Visits" folder)
- Monitoring Visit Form: GET /api/monitoring-visits/latest and GET /api/monitoring-visits
- Monitoring Visit Form: +MV button in operations dashboard clients table
- Incident Report Form: Offline PWA form at `/incident` with 2-section layout (Incident + Investigation/Findings)
- Incident Report Form: Service worker + manifest for installable mobile app
- Incident Report Form: `incident_reports` DB table
- Incident Report Form: POST /api/incident-reports/sync (DB + Google Drive upload to HR/Incident Reports folder)
- Incident Report Form: GET /api/incident-reports/latest and GET /api/incident-reports
- Incident Report Form: +IR button in operations dashboard clients table
- Incident Report Form: +IR button in Employee Portal employee list (EmployeeList.tsx)

## Feb 22, 2026
- Fax: Full fax integration via RingCentral API (replaces $120/yr Fax.Plus)
- Fax: Portal page with Inbox/Sent/Outbox tabs, multi-file upload, cover page/note, drag-and-drop page reorder
- Fax: Inline PDF preview (click any fax row to view without downloading)
- Fax: Telegram + email notifications on inbound fax
- Fax: Gigi tools (send_fax, check_fax_status, list_faxes) across Telegram + Voice channels
- Fax: Both 719-428-3999 and 303-757-1777 can send/receive
- Fax: Auto-sync outbound status from RingCentral on page load
- DB: `fax_log` table with `rc_message_id` column

## Feb 21, 2026
- Client Portal: WellSky prospect→client lifecycle sync (create_prospect, update_prospect_status, convert_prospect_to_client, demographics meta tags)
- Sales Dashboard: auto-sync deals to WellSky on create + stage change (background threads, zero latency impact)
- Sales Dashboard: face sheet scanner on Create Deal card
- Sales Dashboard: Weekly/Monthly/YTD KPIs + Forecast Revenue on Summary dashboard
- Sales Dashboard: Deal/Contact buttons on Dashboard, fixed visit dates and activity logs
- Employee Portal: delete candidate (backend DELETE /admin/cases/{id} + frontend trash icon + confirmation modal)
- Employee Portal: 26/26 UI tests passing, 53/53 E2E tests passing
- Employee Portal: initial git commit + pushed to github.com/shulmeister/employee-portal

## Feb 20, 2026
- Switched all Gigi channels from Gemini to Anthropic Haiku 4.5
- Built shadow mode learning pipeline (gigi/learning_pipeline.py)
- Fixed SMS tool inflation (removed auto-extend block, caregivers get 15 tools only)
- Ran full voice simulation suite (14 scenarios, avg ~50/100)
- Documentation cleanup: consolidated CLAUDE.md, removed stale files

## Feb 19, 2026
- Enterprise readiness: clock in/out tools, transfer rules, shift filling, SMS loop detection, simulation testing
- Fixed simulation bugs: content_complete protocol, cross-process tool capture, Gemini empty-text nudge
- Updated tool counts: Telegram 32, Voice 33, SMS 15, DM/Team 31

## Feb 16, 2026
- Ticket watch system: watch_tickets, list_ticket_watches, remove_ticket_watch
- Ticketmaster + Bandsintown polling, Telegram alerts

## Feb 14, 2026
- Split PowderPulse to standalone port 3003
- Upgraded US resort forecasting: NWS + ECMWF hybrid
- Built Kalshi-Polymarket arb scanner (port 3013)

## Feb 13, 2026
- Weather Sniper Bot deployed (sniper strategy, US cities only)
- Backtested: +345% ROI on US cities

## Feb 8, 2026
- Fixed 17 race condition bugs (asyncio.Lock, to_thread, DB-side NOW())
- Gigi Phases 1-4: Memory, Mode Detector, Failure Handler, Conversation Store, Pattern Detector, Self-Monitor
- Apple Integration: ask-gigi API, Siri Shortcuts, iMessage, Menu Bar, Playwright browser automation

## Feb 7, 2026
- Voice brain validated (6/6 tools passing)
- Multi-LLM provider support (Gemini/Anthropic/OpenAI)
- Fixed Retell WebSocket ping/pong, webhook signature
- 5-agent audit: fixed SQL injection, connection leaks, missing imports

## Feb 6, 2026
- Created 6 Claude Code subagents
- Fixed 27 voice brain bugs, WellSky composite IDs, Retell signature bypass

## Feb 5, 2026
- Added staging environment
- Unified Gigi voice brain via Retell custom-llm WebSocket

## Feb 4, 2026
- Consolidated API credentials, health monitoring, Claude Code integration

## Feb 2, 2026
- Initial Mac Mini self-hosted setup: PostgreSQL, Cloudflare tunnel, Tailscale
