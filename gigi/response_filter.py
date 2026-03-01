"""
Response post-processing filter for Gigi.

Strips hallucinated CLI/install suggestions that Gemini (and sometimes other LLMs)
keep injecting into responses. This is a hard filter applied AFTER LLM generation
on ALL channels (Telegram, RC DM, RC SMS, Ask-Gigi API, Voice).

This exists because system prompt instructions alone do NOT prevent the LLM from
hallucinating "gog CLI", "gcloud CLI", and similar nonsense. The user has been
furious about this for weeks. This filter is non-negotiable.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Phrases that MUST NEVER appear in any Gigi response.
# Case-insensitive matching.
BANNED_PHRASES = [
    "gog cli",
    "gog client",
    "gog",
    "gcloud cli",
    "gcloud",
    "google cloud cli",
    "google cloud sdk",
    "google cloud client",
    "google cloud platform",
    "needs curl",
    "needs firewall",
    "install curl",
    "install gog",
    "install gcloud",
    "install the cli",
    "install/configure",
    "set up gcloud",
    "provide gmail api key",
    "set up the google",
    "configure the google",
    "install the google",
    "google api key",
    "api key for google",
    "googleapis.com/auth",
    "oauth2 credentials",
    "service account",
    "enable the gmail api",
    "enable the calendar api",
    "enable the google",
    "cli tool",
    "command-line tool",
    "command line tool",
    "terminal command",
    "pip install",
    "npm install",
    "brew install",
    "apt install",
    "apt-get install",
    "morning briefing",
    "daily briefing",
    "daily digest",
    "daily pulse",
    "daily summary",
    "morning check-in",
]

# Patterns that indicate a "setup/troubleshooting" section that should be removed
SECTION_HEADERS_TO_STRIP = re.compile(
    r"^(#{1,4}\s*)?(setup|troubleshoot|prerequisite|requirement|install|configuration needed|"
    r"action items?|to.?do|next steps?|getting started|how to fix|"
    r"morning briefing|daily briefing|daily digest)",
    re.IGNORECASE,
)


def strip_markdown_for_voice(text: str) -> str:
    """
    Strip markdown formatting that TTS engines read literally.

    Removes: **bold**, *italic*, `backticks`, # headers, [links](url),
    bullet points (- / * / •), numbered lists (1. 2. 3.),
    and <think>...</think> reasoning blocks from reasoning models.

    This is applied ONLY to voice channel responses.
    """
    if not text:
        return text

    # Strip <think>...</think> reasoning blocks (MiniMax M2.5, DeepSeek, etc.)
    text = strip_thinking_tags(text)

    # Strip bold/italic: **text** → text, *text* → text
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)

    # Strip backticks: `code` → code, ```code``` → code
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)

    # Strip markdown links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Strip header markers: ### Header → Header
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Strip bullet points at line start: - item / * item / • item → item
    text = re.sub(r"^[\s]*[-*•]\s+", "", text, flags=re.MULTILINE)

    # Strip numbered lists: 1. item / 2) item → item
    text = re.sub(r"^[\s]*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Collapse multiple newlines into one (markdown often has double-newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def strip_markdown_for_sms(text: str, max_chars: int = 500) -> str:
    """
    Strip markdown formatting + enforce SMS length limits + remove internal IDs.

    Applied ONLY to SMS channel responses. This is a safety net — the system prompt
    already tells the LLM not to use markdown, but LLMs ignore instructions.

    Strips: **bold**, *italic*, `backticks`, # headers, [links](url),
    bullet points (- / * / •), numbered lists (1. 2. 3.), internal WellSky IDs.
    Enforces max_chars limit with graceful truncation.
    """
    if not text:
        return text

    # Strip bold/italic: **text** → text, *text* → text
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)

    # Strip backticks: `code` → code, ```code``` → code
    text = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", text)

    # Strip markdown links: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Strip header markers: ### Header → Header
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Strip bullet points at line start: - item / * item / • item → item
    text = re.sub(r"^[\s]*[-*•]\s+", "", text, flags=re.MULTILINE)

    # Strip numbered lists: 1. item / 2) item → item
    text = re.sub(r"^[\s]*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Strip internal WellSky IDs: "client ID 8006814", "caregiver_id 12345", etc.
    text = re.sub(
        r"\b(client|caregiver|appointment|patient|practitioner)[_ ]?[Ii][Dd]\s*:?\s*\d+\b",
        "",
        text,
    )

    # Collapse multiple newlines — SMS should be compact
    text = re.sub(r"\n{2,}", "\n", text)

    text = text.strip()

    # Enforce length limit with graceful truncation at sentence boundary
    if len(text) > max_chars:
        truncated = text[:max_chars]
        # Try to break at last sentence boundary
        for sep in [". ", "! ", "? ", "\n"]:
            last_sep = truncated.rfind(sep)
            if last_sep > max_chars // 2:
                truncated = truncated[: last_sep + 1]
                break
        text = truncated.strip()

    return text


def strip_thinking_tags(text: str) -> str:
    """Strip <think>/<thinking> reasoning blocks from reasoning models (MiniMax, DeepSeek, etc.)."""
    if not text:
        return text
    # Quick check — if no angle-bracket tag candidates, skip regex
    text_lower = text.lower()
    if "<think" not in text_lower:
        return text
    # Strip closed think/thinking blocks (case-insensitive)
    text = re.sub(
        r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=re.DOTALL | re.IGNORECASE
    )
    # Strip unclosed think/thinking blocks (model started but didn't close tag)
    text = re.sub(r"<think(?:ing)?>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def strip_banned_content(text: str) -> str:
    """
    Remove any lines/sections containing banned CLI/install references.

    This is the LAST line of defense. It runs after LLM generation on every
    single response across all channels. If the LLM hallucinates CLI garbage,
    this catches it.

    Returns:
        Cleaned text, or a fallback message if the entire response was garbage.
    """
    if not text:
        return text

    # Strip reasoning blocks FIRST (before any other processing)
    text = strip_thinking_tags(text)

    text_lower = text.lower()

    # Quick check — if no banned phrases found, return as-is (fast path)
    if not any(bp in text_lower for bp in BANNED_PHRASES):
        return text

    # Banned content detected — strip it line by line
    logger.warning(
        "BANNED CONTENT DETECTED in LLM response — stripping hallucinated CLI references"
    )

    lines = text.split("\n")
    cleaned = []
    skip_section = False

    for line in lines:
        ll = line.lower().strip()

        # Check if this line contains any banned phrase
        has_banned = any(bp in ll for bp in BANNED_PHRASES)

        # Check if this is a setup/troubleshooting section header
        is_setup_header = bool(SECTION_HEADERS_TO_STRIP.match(ll))

        # Check if this is a checklist item (often part of hallucinated setup steps)
        is_checklist = (
            ll.startswith("• [ ]") or ll.startswith("- [ ]") or ll.startswith("* [ ]")
        )

        if has_banned or is_setup_header or is_checklist:
            skip_section = True
            continue

        # If we're in a skip section, keep skipping continuation lines
        # (bullets, numbered items, indented lines, empty lines)
        if skip_section:
            if (
                ll.startswith("•")
                or ll.startswith("-")
                or ll.startswith("*")
                or ll.startswith("  ")
                or ll.startswith("\t")
                or re.match(r"^\d+[\.\)]\s", ll)
                or ll == ""
            ):
                continue
            # Non-continuation line — stop skipping
            skip_section = False

        cleaned.append(line)

    result = "\n".join(cleaned).strip()

    if not result:
        result = "Here's what I found. Let me know if you need anything else."
        logger.warning("Entire LLM response was banned content — used fallback")

    return result
