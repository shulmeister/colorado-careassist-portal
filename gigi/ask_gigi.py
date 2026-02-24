"""
Generic Ask-Gigi API — Foundation for Apple Shortcuts, Siri, iMessage, Menu Bar, etc.

Provides a single async function `ask_gigi()` that:
- Accepts text input from any channel
- Runs Gigi's full LLM pipeline with tool calling
- Returns the response text

Reuses GigiTelegramBot's execute_tool (600+ lines of tool implementations)
without duplication. All 19 tools available across all channels.
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("gigi.ask_gigi")

# Lazy-loaded singleton — avoids import-time side effects
_bot_instance = None


def _get_bot():
    """Lazy-initialize a GigiTelegramBot instance for tool execution reuse."""
    global _bot_instance
    if _bot_instance is None:
        from gigi.telegram_bot import GigiTelegramBot
        _bot_instance = GigiTelegramBot()
        logger.info("Ask-Gigi: initialized shared bot instance for tool execution")
    return _bot_instance


def _build_system_prompt(channel: str, conversation_store=None, user_message=None):
    """Build system prompt with dynamic context, adapted for the given channel."""
    from gigi.telegram_bot import (
        _TELEGRAM_SYSTEM_PROMPT_BASE,
        MEMORY_AVAILABLE,
        MODE_AVAILABLE,
        _memory_system,
        _mode_detector,
    )

    parts = [_TELEGRAM_SYSTEM_PROMPT_BASE]

    # Current date/time
    parts.append(f"\n# Current Date\nToday is {datetime.now().strftime('%A, %B %d, %Y')}")
    parts.append(f"\n# Channel\nThis conversation is via the '{channel}' channel.")

    # Inject mode context
    if MODE_AVAILABLE and _mode_detector:
        try:
            mode_info = _mode_detector.get_current_mode()
            parts.append(f"\n# Current Operating Mode\nMode: {mode_info.mode.value.upper()} (source: {mode_info.source.value})")
        except Exception as e:
            logger.warning(f"Mode detection failed: {e}")

    # Inject relevant memories
    if MEMORY_AVAILABLE and _memory_system:
        try:
            memories = _memory_system.query_memories(min_confidence=0.5, limit=25)
            if memories:
                memory_lines = [f"- {m.content} (confidence: {m.confidence:.0%}, category: {m.category})" for m in memories]
                parts.append("\n# Your Saved Memories\n" + "\n".join(memory_lines))
        except Exception as e:
            logger.warning(f"Memory injection failed: {e}")

    # Inject cross-channel context
    if conversation_store:
        try:
            xc = conversation_store.get_cross_channel_summary("jason", channel, limit=5, hours=24)
            if xc:
                parts.append(xc)
            # Long-term conversation history (summaries from past 30 days)
            ltc = conversation_store.get_long_term_context("jason", days=30)
            if ltc:
                parts.append(ltc)
        except Exception as e:
            logger.warning(f"Cross-channel context failed: {e}")

    return "\n".join(parts)


async def ask_gigi(text: str, user_id: str = "jason", channel: str = "api") -> str:
    """
    Send a message to Gigi and get a response with full tool support.

    Args:
        text: The user's message
        user_id: User identifier (default "jason")
        channel: Channel name (api, shortcut, siri, imessage, menubar, etc.)

    Returns:
        Gigi's response text
    """
    from gigi.telegram_bot import (
        LLM_PROVIDER,
    )

    bot = _get_bot()
    store = bot.conversation_store

    # Store user message
    store.append(user_id, channel, "user", text)

    # Build system prompt with cross-channel context
    sys_prompt = _build_system_prompt(channel, store, user_message=text)

    # Get conversation history for this channel
    history = store.get_recent(user_id, channel, limit=20)

    try:
        # Fallback chain: primary provider → anthropic haiku on rate limit
        try:
            if LLM_PROVIDER == "gemini":
                response_text = await _call_gemini(bot, history, sys_prompt)
            elif LLM_PROVIDER == "openai":
                response_text = await _call_openai(bot, history, sys_prompt)
            else:
                response_text = await _call_anthropic(bot, history, sys_prompt)
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = any(k in err_str for k in ("429", "resource_exhausted", "rate_limit", "quota"))
            if is_rate_limit and LLM_PROVIDER != "anthropic":
                logger.warning(f"Ask-Gigi {LLM_PROVIDER} rate limited, falling back to anthropic: {e}")
                response_text = await _call_anthropic(bot, history, sys_prompt)
            else:
                raise
    except Exception as e:
        logger.error(f"Ask-Gigi LLM error ({LLM_PROVIDER}): {e}", exc_info=True)
        response_text = f"Sorry, I hit an error: {str(e)}"

    if not response_text:
        response_text = "I processed your request but have no text response."

    # Strip hallucinated CLI/install suggestions (Gemini keeps adding these)
    from gigi.response_filter import strip_banned_content
    response_text = strip_banned_content(response_text)

    # Store assistant response
    store.append(user_id, channel, "assistant", response_text)

    return response_text


async def _call_gemini(bot, history, sys_prompt):
    """Gemini tool-calling loop (mirrors telegram_bot._call_gemini without Telegram deps)."""
    from google.genai import types as genai_types

    from gigi.telegram_bot import GEMINI_TOOLS, LLM_MODEL

    contents = []
    for m in history:
        role = "user" if m["role"] == "user" else "model"
        contents.append(genai_types.Content(
            role=role,
            parts=[genai_types.Part(text=m["content"])]
        ))

    config = genai_types.GenerateContentConfig(
        system_instruction=sys_prompt,
        tools=GEMINI_TOOLS,
    )

    response = bot.llm.models.generate_content(
        model=LLM_MODEL, contents=contents, config=config
    )

    max_rounds = 5
    fn_response_parts = []
    for tool_round in range(max_rounds):
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part)

        if not function_calls:
            break

        logger.info(f"Ask-Gigi tool round {tool_round + 1} (gemini)")
        contents.append(response.candidates[0].content)

        fn_response_parts = []
        for part in function_calls:
            fc = part.function_call
            tool_input = dict(fc.args) if fc.args else {}
            logger.info(f"  Tool: {fc.name} input: {tool_input}")
            result_str = await bot.execute_tool(fc.name, tool_input)
            logger.info(f"  Result: {result_str[:200]}...")

            try:
                result_data = json.loads(result_str)
            except (json.JSONDecodeError, TypeError):
                result_data = {"result": result_str}

            fn_response_parts.append(
                genai_types.Part.from_function_response(
                    name=fc.name, response=result_data
                )
            )

        contents.append(genai_types.Content(role="user", parts=fn_response_parts))

        response = bot.llm.models.generate_content(
            model=LLM_MODEL, contents=contents, config=config
        )

    text_parts = []
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text_parts.append(part.text)
    final = "".join(text_parts)

    # Safety net: if Gemini returned no text after tool calls, use last tool result
    if not final and fn_response_parts:
        logger.warning("Ask-Gigi: Gemini returned no text after tool call — using tool result as fallback")
        last_part = fn_response_parts[-1]
        if hasattr(last_part, 'function_response') and last_part.function_response:
            fr = last_part.function_response
            resp_data = fr.response if hasattr(fr, 'response') else {}
            if isinstance(resp_data, dict):
                final = json.dumps(resp_data, indent=2, default=str)
            else:
                final = str(resp_data)
    return final


async def _call_anthropic(bot, history, sys_prompt):
    """Anthropic tool-calling loop."""
    from gigi.telegram_bot import ANTHROPIC_TOOLS, LLM_MODEL

    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    response = bot.llm.messages.create(
        model=LLM_MODEL, max_tokens=4096,
        system=sys_prompt, tools=ANTHROPIC_TOOLS,
        messages=messages
    )

    max_rounds = 5
    for tool_round in range(max_rounds):
        if response.stop_reason != "tool_use":
            break
        logger.info(f"Ask-Gigi tool round {tool_round + 1} (anthropic)")

        tool_results = []
        assistant_content = []

        for block in response.content:
            if block.type == "tool_use":
                logger.info(f"  Tool: {block.name} input: {block.input}")
                result = await bot.execute_tool(block.name, block.input)
                logger.info(f"  Result: {result[:200]}...")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input
                })
            elif block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        response = bot.llm.messages.create(
            model=LLM_MODEL, max_tokens=4096,
            system=sys_prompt, tools=ANTHROPIC_TOOLS,
            messages=messages
        )

    return "".join(b.text for b in response.content if b.type == "text")


async def _call_openai(bot, history, sys_prompt):
    """OpenAI tool-calling loop."""
    from gigi.telegram_bot import LLM_MODEL, OPENAI_TOOLS

    messages = [{"role": "system", "content": sys_prompt}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})

    response = bot.llm.chat.completions.create(
        model=LLM_MODEL, messages=messages, tools=OPENAI_TOOLS
    )

    max_rounds = 5
    for tool_round in range(max_rounds):
        choice = response.choices[0]
        if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
            break

        logger.info(f"Ask-Gigi tool round {tool_round + 1} (openai)")
        messages.append(choice.message)

        for tc in choice.message.tool_calls:
            tool_input = json.loads(tc.function.arguments)
            logger.info(f"  Tool: {tc.function.name} input: {tool_input}")
            result_str = await bot.execute_tool(tc.function.name, tool_input)
            logger.info(f"  Result: {result_str[:200]}...")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str
            })

        response = bot.llm.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=OPENAI_TOOLS
        )

    return response.choices[0].message.content or ""
