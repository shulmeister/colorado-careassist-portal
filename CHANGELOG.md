# Changelog

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
