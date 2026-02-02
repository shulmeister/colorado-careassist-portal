# GIGI State Documentation

## Current Status: ✅ STABLE & CAPABLE (Currently Disabled)

**Date:** February 1, 2026
**Bot Mode:** Embedded (Trojan Horse)
**Polling:** 5 seconds
**AI:** Google Gemini (Connected)

### Capabilities
1.  **SMS:** Replies smartly using Gemini. Recognizes Owner ("Hi Jason"). No duplicates.
2.  **Voice:** Recognizes callers via WellSky lookup ("Hi [Name]").
3.  **Logging:** Logs ALL interactions to WellSky (Client Notes or Admin Tasks).

### Known Issues
- **Disabled:** Bot is commented out in `unified_app.py` to prevent noise until Mac Mini migration.
- **WellSky Data:** Gigi can *write* to WellSky fine, but she might have trouble *finding* specific clients if the API keeps returning "0 Active Clients". However, she falls back to generic Admin Tasks, so no data is lost.

### Deployment
- **Credentials:** Hardcoded in `gigi/async_bot.py`.
- **Run:** Uncomment startup line in `unified_app.py` and push to main.