"""
Partial Availability Parser

Handles scenarios like:
"I can't work with Judy tomorrow but I could do 8:30 to 11:30"

Detects:
1. Cancellation/call-out
2. Alternative time offer
3. Parses the offered time window
"""
import re
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)


class PartialAvailability:
    """Represents a partial availability offer"""
    def __init__(
        self,
        is_cancelling: bool,
        offers_alternative: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        raw_time_text: Optional[str] = None
    ):
        self.is_cancelling = is_cancelling
        self.offers_alternative = offers_alternative
        self.start_time = start_time
        self.end_time = end_time
        self.raw_time_text = raw_time_text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_cancelling": self.is_cancelling,
            "offers_alternative": self.offers_alternative,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "raw_time_text": self.raw_time_text
        }

    def __repr__(self):
        if self.offers_alternative:
            return f"PartialAvailability(cancel=True, alternative={self.start_time}-{self.end_time})"
        return f"PartialAvailability(cancel={self.is_cancelling})"


def parse_time_string(time_str: str) -> Optional[str]:
    """
    Parse a time string like "8:30", "2pm", "11:30am" into 24-hour format.

    Returns:
        Time in HH:MM format (e.g., "08:30", "14:00") or None if can't parse
    """
    time_str = time_str.strip().lower().replace(" ", "")

    # Pattern: 8:30am, 2:00pm, 14:30, etc.
    patterns = [
        # 8:30am, 2:00pm
        (r'(\d{1,2}):(\d{2})\s*(am|pm)', lambda m: convert_to_24h(int(m.group(1)), int(m.group(2)), m.group(3))),
        # 8am, 2pm
        (r'(\d{1,2})\s*(am|pm)', lambda m: convert_to_24h(int(m.group(1)), 0, m.group(2))),
        # 14:30 (already 24-hour)
        (r'(\d{1,2}):(\d{2})$', lambda m: f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"),
        # 8:30 (assume PM if > 12, AM if <= 12)
        (r'(\d{1,2}):(\d{2})$', lambda m: guess_am_pm(int(m.group(1)), int(m.group(2)))),
    ]

    for pattern, converter in patterns:
        match = re.search(pattern, time_str)
        if match:
            try:
                return converter(match)
            except Exception as e:
                logger.warning(f"Failed to convert time '{time_str}': {e}")
                continue

    return None


def convert_to_24h(hour: int, minute: int, meridiem: str) -> str:
    """Convert 12-hour time to 24-hour format"""
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def guess_am_pm(hour: int, minute: int) -> str:
    """
    Guess AM/PM when not specified.
    Assume: 7-11 = morning, 12-6 = afternoon/evening, 1-6 = afternoon
    """
    if 7 <= hour <= 11:
        return f"{hour:02d}:{minute:02d}"  # Morning - keep as is
    elif hour == 12:
        return f"{hour:02d}:{minute:02d}"  # Noon
    elif 1 <= hour <= 6:
        # Could be PM afternoon (most common for caregiving)
        return f"{hour + 12:02d}:{minute:02d}"
    else:
        return f"{hour:02d}:{minute:02d}"


def extract_time_window(text: str) -> Optional[Tuple[str, str, str]]:
    """
    Extract time window from text like:
    - "8:30 to 11:30"
    - "from 2pm to 6pm"
    - "8:30-11:30"
    - "after 2pm"
    - "until 4"
    - "between 9 and 12"

    Returns:
        (start_time, end_time, raw_text) or None
    """

    # Pattern 1: "8:30 to 11:30", "2pm-6pm", "from 8 to 11"
    pattern1 = r'(?:from\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
    match = re.search(pattern1, text, re.IGNORECASE)
    if match:
        raw_text = match.group(0)
        start = parse_time_string(match.group(1))
        end = parse_time_string(match.group(2))
        if start and end:
            return (start, end, raw_text)

    # Pattern 2: "after 2pm"
    pattern2 = r'after\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
    match = re.search(pattern2, text, re.IGNORECASE)
    if match:
        raw_text = match.group(0)
        start = parse_time_string(match.group(1))
        if start:
            return (start, "end_of_day", raw_text)

    # Pattern 3: "until 4pm"
    pattern3 = r'until\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
    match = re.search(pattern3, text, re.IGNORECASE)
    if match:
        raw_text = match.group(0)
        end = parse_time_string(match.group(1))
        if end:
            return ("start_of_day", end, raw_text)

    # Pattern 4: "between 9 and 12"
    pattern4 = r'between\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+and\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
    match = re.search(pattern4, text, re.IGNORECASE)
    if match:
        raw_text = match.group(0)
        start = parse_time_string(match.group(1))
        end = parse_time_string(match.group(2))
        if start and end:
            return (start, end, raw_text)

    return None


def detect_partial_availability(message: str) -> PartialAvailability:
    """
    Detect if message contains a cancellation + alternative time offer.

    Examples:
    - "I can't work with Judy tomorrow but I could do 8:30 to 11:30"
    - "I'm sick, can't make my 2pm shift but I can do 4-6pm"
    - "I need to cancel but I'm available after 3"

    Returns:
        PartialAvailability object with parsed details
    """
    msg_lower = message.lower()

    # Check for cancellation/call-out indicators
    is_cancelling = any(phrase in msg_lower for phrase in [
        "can't make it", "cant make it", "won't make it", "wont make it",
        "not going to be able to work", "need to cancel", "have to cancel",
        "can't come in", "cant come in", "can't work", "cant work",
        "forgot that i have", "i have an appointment"
    ])

    # Check for alternative offer indicators
    offers_alternative = any(phrase in msg_lower for phrase in [
        "but i could do", "but i can do", "i could do", "i can do",
        "available from", "available after", "available until",
        "available between", "free from", "free after"
    ])

    # If they're offering an alternative, extract the time window
    start_time = None
    end_time = None
    raw_time_text = None

    if offers_alternative or "could do" in msg_lower or "can do" in msg_lower:
        time_window = extract_time_window(message)
        if time_window:
            start_time, end_time, raw_time_text = time_window
            offers_alternative = True  # Confirm they're offering alternative

    return PartialAvailability(
        is_cancelling=is_cancelling,
        offers_alternative=offers_alternative,
        start_time=start_time,
        end_time=end_time,
        raw_time_text=raw_time_text
    )


# Test cases
if __name__ == "__main__":
    test_messages = [
        # Dina's exact message from screenshot
        "Hi there...I need to let you know that I'm not going to be able to work with Judy tomorrow...almost forgot that I have an appointment I'm sorry I could do 8:30to 11:30",

        # Other scenarios
        "I'm sick, can't make my 2pm shift but I can do 4-6pm",
        "I need to cancel but I'm available after 3pm",
        "Can't work the full day but I can do until 2",
        "I have an appointment until noon but I could do 12:30-5pm",
        "Not going to make it but I'm free from 10am to 1pm",

        # Should NOT trigger
        "I'm sick, can't make it",
        "I'll be there at 2pm",
    ]

    print("="*80)
    print("PARTIAL AVAILABILITY PARSER - TEST CASES")
    print("="*80)

    for i, msg in enumerate(test_messages, 1):
        print(f"\n[Test {i}]")
        print(f"Message: \"{msg[:70]}{'...' if len(msg) > 70 else ''}\"")

        result = detect_partial_availability(msg)

        print(f"Result: {result}")
        print(f"  • Cancelling: {result.is_cancelling}")
        print(f"  • Offers alternative: {result.offers_alternative}")
        if result.offers_alternative:
            print(f"  • Time window: {result.start_time} - {result.end_time}")
            print(f"  • Raw text: \"{result.raw_time_text}\"")

        # Recommendation for Gigi
        if result.offers_alternative:
            print(f"  → GIGI ACTION: Escalate to coordinator with parsed time: {result.start_time}-{result.end_time}")
        elif result.is_cancelling:
            print(f"  → GIGI ACTION: Handle as normal call-out")
        else:
            print(f"  → GIGI ACTION: General response")

    print("\n" + "="*80)
    print("✅ Parser ready for integration into Gigi")
    print("="*80)
