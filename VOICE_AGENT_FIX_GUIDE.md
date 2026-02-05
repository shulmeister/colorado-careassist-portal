# Voice Agent Fix Implementation Guide

## Problem Summary
Jason called the voice agent (+17208176600) and was hung up on when asking for weather. The agent needs to:
1. Look up caller ID in Apple Contacts
2. Transfer known contacts to Jason
3. Take messages from unknown callers
4. Handle weather requests without hanging up

## Solution Architecture

### Components Created
1. **enhanced_webhook.py** - Core logic for caller lookup, greetings, transfers, messages
2. **apple_contacts_lookup.py** - Mac node integration (placeholder for future implementation)
3. **retell_tools_schema_updated.json** - New tool definitions
4. **deploy_voice_agent_fix.sh** - Automated deployment script

### Caller Flow
```
Incoming Call
   ↓
Check Database/Cache
   ↓
Check Apple Contacts (Mac node)
   ↓
├─ Known Contact (Jason/Jennifer/etc.)
│  → Greet by name
│  → Transfer to Jason (+16039971495)
│
└─ Unknown Caller
   → Take message
   → Send to Telegram (ID: 8215335898)
```

## Manual Implementation Steps

### Step 1: Update main.py Imports
Add these imports after the existing imports (around line 30):

```python
# Enhanced webhook functionality
from enhanced_webhook import (
    CallerLookupService, generate_greeting, transfer_call,
    send_telegram_message, handle_message_received, get_weather
)
```

### Step 2: Add Configuration Constants
Add near the top configuration section (around line 75):

```python
# Jason's contact info
JASON_PHONE = "+16039971495"
```

### Step 3: Update call_started Webhook Handler
Replace the `call_started` section (around line 2752) with:

```python
    if event == "call_started":
        from_number = body.get("from_number", "")
        to_number = body.get("to_number", "")
        logger.info(f"Call started from {from_number} to {to_number}")

        # Enhanced caller lookup with Apple Contacts fallback
        lookup_service = CallerLookupService(
            db_lookup_fn=lambda phone: _lookup_in_database(phone),
            cache_lookup_fn=lambda phone: _lookup_in_cache(phone)
        )
        
        caller_info = lookup_service.lookup(from_number)
        
        # Generate personalized greeting
        greeting = generate_greeting(caller_info)
        
        # Store in call context for later reference
        _store_call_context(call_id, caller_info)
        
        # Log the lookup result
        if caller_info.get("found"):
            name = caller_info.get("name", "Unknown")
            source = caller_info.get("source", "unknown")
            logger.info(f"AUTO-LOOKUP: Found {name} via {source}")
        else:
            logger.info(f"AUTO-LOOKUP: Unknown caller {from_number}")
        
        # Prepare response with greeting and instructions
        response_data = {
            "status": "ok",
            "caller_info": caller_info,
            "initial_greeting": greeting
        }
        
        # If this is a known caller (including Jason), prepare for transfer
        if caller_info.get("should_transfer"):
            response_data["action"] = "greet_and_transfer"
            logger.info(f"Will transfer call to Jason after greeting")
        elif caller_info.get("take_message"):
            response_data["action"] = "take_message"
            logger.info("Unknown caller - will take message")
        
        return JSONResponse(response_data)
```

### Step 4: Add New Tool Handlers
In the `tool_call` event handler (around line 2820), add these new tool handlers:

```python
                elif tool_name == "get_weather":
                    location = tool_args.get("location", "Boulder CO")
                    weather_result = get_weather(location)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": weather_result
                    })
                    logger.info(f"Weather requested for {location}: {weather_result}")

                elif tool_name == "transfer_to_jason":
                    # Transfer the call to Jason
                    success = transfer_call(call_id, JASON_PHONE)
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": success,
                            "message": "Transferring you to Jason now" if success else "I'm having trouble transferring right now"
                        }
                    })
                    logger.info(f"Transfer initiated: {'success' if success else 'failed'}")

                elif tool_name == "take_message":
                    # Take a message from unknown caller
                    caller_phone = tool_args.get("caller_phone", "Unknown")
                    caller_name = tool_args.get("caller_name", "")
                    message_text = tool_args.get("message", "")
                    
                    # Format message info
                    caller_info = {
                        "phone": caller_phone,
                        "name": caller_name,
                        "type": "unknown"
                    }
                    
                    # Send to Telegram
                    handle_message_received(caller_info, message_text, call_id)
                    
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": True,
                            "message": "I've sent your message to Jason. He'll get back to you as soon as possible."
                        }
                    })
                    logger.info(f"Message taken from {caller_phone}")
```

### Step 5: Add Helper Function (if needed)
Add this helper function if `_lookup_in_database` doesn't exist:

```python
def _lookup_in_database(clean_phone: str) -> Optional[Dict]:
    """Lookup in database - wrapper for existing functionality"""
    db = _get_db()
    if db:
        try:
            return db.lookup_caller(clean_phone)
        except Exception as e:
            logger.warning(f"Database lookup failed: {e}")
    return None
```

## Deployment

### Quick Deploy (Automated)
```bash
cd ~/clawd/careassist-unified
./deploy_voice_agent_fix.sh
```

### Manual Deploy Steps
```bash
# 1. Commit changes
git add gigi/enhanced_webhook.py gigi/apple_contacts_lookup.py gigi/retell_tools_schema.json
git commit -m "Fix voice agent: Add caller ID, transfer, weather, and message taking"

# 2. Deploy to Mac Mini
git push origin main

# 3. Sync tools with Retell AI
cd gigi
python3 sync_retell.py
cd ..

# 4. Verify deployment
curl https://portal.coloradocareassist.com/gigi/health
```

## Testing Checklist

### Test 1: Known Caller (Jason)
- [ ] Call +17208176600 from +16039971495
- [ ] Verify greeting: "Hi Jason!"
- [ ] Verify transfer works
- [ ] Verify no hang-up

### Test 2: Weather Request
- [ ] Call from any number
- [ ] Ask "What's the weather in Boulder?"
- [ ] Verify proper weather response
- [ ] Verify no hang-up

### Test 3: Unknown Caller Message
- [ ] Call from unknown number
- [ ] Request to leave message
- [ ] Verify message recorded
- [ ] Check Telegram (ID: 8215335898) for notification

### Test 4: Known Contact Transfer
- [ ] Call from number in Apple Contacts (once Mac node connected)
- [ ] Verify greeting by name
- [ ] Verify transfer to Jason

## Mac Node Integration (Future)

The Apple Contacts lookup is currently a placeholder. To complete:

1. **Ensure Mac Node is online:**
   ```bash
   # Check node status
   clawdbot nodes status
   ```

2. **Install apple-contacts skill on Mac:**
   ```bash
   ssh jason@mac-node
   cd ~/.clawdbot/skills
   git clone https://github.com/clawdbot/skills-apple-contacts apple-contacts
   ```

3. **Update apple_contacts_lookup.py:**
   - Implement actual Mac node API calls
   - Use clawdbot nodes API to execute AppleScript
   - Cache results for performance

## Configuration

### Environment Variables (Mac Mini)
```bash
# Already configured:
RETELL_API_KEY=key_5d0bc4168659a5df305b8ac2a7fd

# May need to add:
TELEGRAM_BOT_TOKEN=8508806105:AAExZ25ZN19X3xjBQAZ3Q9fHgAQmWWklX8U
TELEGRAM_CHAT_ID=8215335898
JASON_PHONE=+16039971495
```

### Phone Numbers
- **Voice Agent (Personal):** +17208176600
- **Voice Agent (Business):** +17194274641
- **Jason's Phone:** +16039971495

### Retell AI Agent IDs
- **Personal Agent:** agent_e54167532428a1bc72c3375417
- **Business Agent:** agent_d5c3f32bdf48fa4f7f24af7d36

## Rollback Plan

If issues occur:

```bash
# Restore from backup
cp gigi/main.py.backup.[timestamp] gigi/main.py
cp gigi/retell_tools_schema.json.backup.[timestamp] gigi/retell_tools_schema.json

# Redeploy
git add gigi/main.py gigi/retell_tools_schema.json
git commit -m "Rollback voice agent changes"
git push origin main
cd gigi && python3 sync_retell.py && cd ..
```

## Troubleshooting

### Call immediately hangs up
- Check webhook logs: `tail -f ~/logs/gigi-unified.log -a careassist-unified`
- Verify tool handlers are added correctly
- Check Retell dashboard for errors

### Transfer not working
- Verify JASON_PHONE constant is set
- Check Retell API key is valid
- Review transfer_call function logs

### Messages not reaching Telegram
- Verify TELEGRAM_BOT_TOKEN is correct
- Check TELEGRAM_CHAT_ID matches Jason's chat
- Test manually: `curl https://api.telegram.org/bot[TOKEN]/getUpdates`

### Weather not responding
- Test endpoint: `curl https://portal.coloradocareassist.com/api/gigi/voice/weather`
- Check Open-Meteo API is accessible
- Review location mapping in get_weather function

## Success Criteria

✅ Jason can call and be greeted by name  
✅ Transfer to Jason works for known contacts  
✅ Weather requests are handled without hanging up  
✅ Unknown callers can leave messages  
✅ Messages appear in Telegram  
✅ No critical failures or hang-ups  

## Next Steps

1. Complete manual code integration in main.py
2. Deploy to Mac Mini
3. Test all scenarios
4. Connect Mac node for Apple Contacts
5. Monitor initial calls for issues
6. Iterate based on feedback
