# RingCentral Embeddable Widget Configuration

## Final Working Configuration

### What's Enabled
- ✅ **Phone** - Dialpad for making calls
- ✅ **Text** - SMS messaging
- ✅ **Chat** - Team messaging (Glip)
- ✅ **Contacts** - Contact list
- ✅ **Dark Theme** - Matches dashboard

### What's Disabled
- ❌ Video/Conferences
- ❌ Fax (appears based on account settings, not controlled by config)

### URL Parameters in Use
```python
params = {
    "clientId": RINGCENTRAL_EMBED_CLIENT_ID,
    "appServer": RINGCENTRAL_EMBED_SERVER,
    "defaultTab": "messages",  # Opens to Chat by default
    "redirectUri": "https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html",
    "enableGlip": "true",       # Enable Chat/Glip tab
    "disableGlip": "false",     # Ensure Glip is not disabled
    "disableConferences": "true",  # Disable video/meetings
    "theme": "dark"             # Set dark theme
}
```

### Environment Variables
```bash
RINGCENTRAL_EMBED_CLIENT_ID=ZqSbXoLcq6zbaRK0t7NSqG
RINGCENTRAL_EMBED_SERVER=https://platform.ringcentral.com
RINGCENTRAL_EMBED_APP_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/app.html
RINGCENTRAL_EMBED_ADAPTER_URL=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/adapter.js
RINGCENTRAL_EMBED_DEFAULT_TAB=messages
RINGCENTRAL_EMBED_REDIRECT_URI=https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html
```

### RingCentral Developer Portal Setup
1. App Type: **Browser-Based / Client-side web app (SPA)**
2. OAuth Flow: **3-legged OAuth authorization code with PKCE**
3. Redirect URI: `https://apps.ringcentral.com/integration/ringcentral-embeddable/latest/redirect.html`
4. Required Scopes:
   - VoIP Calling
   - Read Messages
   - Edit Messages
   - Internal Messages
   - Team Messaging

### File Locations
- **Backend Config**: `portal_app.py` (lines 26-41, 147-161)
- **Frontend**: `templates/portal.html` (lines 863-890)
- **Documentation**: `README.md` (lines 33-52, 80-87)

### Git Status
- ✅ Latest changes committed: `d6981dd`
- ✅ Deployed to Heroku: v75
- ✅ Local and Heroku in sync

### Important Notes
1. **Text tab requires SMS enabled** on your RingCentral account
2. **Chat requires Team Messaging/Glip** subscription
3. Both `enableGlip=true` and `disableGlip=false` are needed to ensure Chat shows alongside Text
4. The widget is embedded in the left sidebar and always visible on portal pages
5. Dark theme is automatically applied to match the dashboard

### Troubleshooting
If tabs disappear:
- Verify your RingCentral account has the required features enabled
- Check that URL parameters haven't changed
- Ensure browser cache is cleared (hard refresh: Shift+Reload)


