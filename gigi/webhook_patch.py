"""
Webhook Enhancement Patch
Instructions to update main.py with enhanced caller ID and transfer logic
"""

# Add these imports at the top of main.py
IMPORT_ADDITIONS = """
from enhanced_webhook import (
    CallerLookupService, 
    generate_greeting,
    transfer_call,
    send_telegram_message,
    handle_message_received,
    get_weather
)
"""

# Replace the call_started handler (around line 2752) with this enhanced version
CALL_STARTED_REPLACEMENT = """
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
        
        # Prepare response with greeting and transfer instructions
        response_data = {
            "status": "ok",
            "caller_info": caller_info,
            "initial_greeting": greeting
        }
        
        # If this is a known caller (including Jason), prepare for transfer
        if caller_info.get("should_transfer"):
            # Note: Actual transfer happens after greeting
            # Retell agent will use transfer_call function tool
            response_data["action"] = "greet_and_transfer"
            logger.info(f"Will transfer call to Jason after greeting")
        elif caller_info.get("take_message"):
            # Unknown caller - take message
            response_data["action"] = "take_message"
            logger.info("Unknown caller - will take message")
        
        return JSONResponse(response_data)
"""

# Add weather tool handling in the tool_call section
WEATHER_TOOL_ADDITION = """
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
                    message_text = tool_args.get("message", "")
                    
                    # Send to Telegram
                    handle_message_received(
                        {"phone": caller_phone, "type": "unknown"},
                        message_text,
                        call_id
                    )
                    
                    results.append({
                        "tool_call_id": tool_call_id,
                        "result": {
                            "success": True,
                            "message": "I've sent your message to Jason. He'll get back to you as soon as possible."
                        }
                    })
                    logger.info(f"Message taken from {caller_phone}")
"""

# Helper function additions
HELPER_FUNCTIONS = """
def _lookup_in_database(clean_phone: str) -> Optional[Dict]:
    '''Lookup in database - wrapper for existing functionality'''
    db = _get_db()
    if db:
        try:
            return db.lookup_caller(clean_phone)
        except Exception as e:
            logger.warning(f"Database lookup failed: {e}")
    return None
"""

# Instructions for manual patching
MANUAL_INSTRUCTIONS = """
MANUAL PATCHING INSTRUCTIONS FOR gigi/main.py:

1. Add imports at top (after existing imports):
   from enhanced_webhook import (
       CallerLookupService, generate_greeting, transfer_call,
       send_telegram_message, handle_message_received, get_weather
   )

2. Add JASON_PHONE constant near top configuration:
   JASON_PHONE = "+16039971495"

3. Replace call_started handler (line ~2752) with enhanced version from CALL_STARTED_REPLACEMENT

4. Add weather and transfer tools in tool_call handler (line ~2820) from WEATHER_TOOL_ADDITION

5. Add helper function _lookup_in_database if it doesn't exist

6. Test the changes before deploying!
"""

print(MANUAL_INSTRUCTIONS)
