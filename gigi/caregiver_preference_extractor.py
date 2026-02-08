"""
Caregiver Preference Extractor

Uses LLM (Gemini or Claude) to mine caregiver preferences from SMS/chat messages
and stores them in gigi_memories for use by the shift filling matcher.

Preference types:
- schedule: "can't work Thursdays", "only mornings", "no weekends"
- client: "loves working with Mrs. Smith", "won't go back to that house"
- location: "won't drive to Boulder", "prefers Aurora area"
- general: "needs 24h notice", "prefers longer shifts"
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

# Multi-LLM support — use whatever provider is configured
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)

CAREGIVER_MEMORY_ENABLED = os.getenv("CAREGIVER_MEMORY_ENABLED", "false").lower() == "true"

EXTRACTION_PROMPT = """Analyze this message from caregiver {name} (ID: {caregiver_id}).
Extract any scheduling preferences, client preferences, or location preferences.

Message: "{message}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "preferences": [
    {{
      "type": "schedule|client|location|general",
      "content": "short description of the preference",
      "hard_constraint": true/false,
      "day_of_week": null or "monday|tuesday|...|sunday",
      "time_preference": null or "morning|afternoon|evening|overnight",
      "client_name": null or "client name if mentioned",
      "location": null or "city/area name"
    }}
  ]
}}

Rules:
- Only extract CLEAR preferences, not temporary situations (e.g. "sick today" is NOT a preference)
- hard_constraint=true means they absolutely won't/can't do something (e.g. "I can NEVER work Thursdays")
- hard_constraint=false means they prefer not to but could (e.g. "I'd rather not work weekends")
- If no preferences detected, return {{"preferences": []}}
- Do NOT invent preferences that aren't clearly stated"""


class CaregiverPreferenceExtractor:
    """Extracts and stores caregiver preferences from free-text messages."""

    def __init__(self, memory_system, llm_provider: str = None, api_key: str = None):
        self.memory = memory_system
        self.llm_provider = llm_provider or os.getenv("GIGI_LLM_PROVIDER", "gemini")
        if self.llm_provider == "gemini" and GEMINI_AVAILABLE:
            self.gemini_client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
            self.anthropic_client = None
        elif self.llm_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            self.anthropic_client = anthropic.Anthropic(
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
            )
            self.gemini_client = None
        else:
            raise RuntimeError(f"LLM provider '{self.llm_provider}' not available")

    async def extract_and_store(
        self,
        caregiver_id: str,
        caregiver_name: str,
        message_text: str
    ) -> List[str]:
        """
        Extract preferences from a message and store in gigi_memories.

        Returns list of memory IDs created/reinforced.
        """
        if not CAREGIVER_MEMORY_ENABLED:
            return []

        if not message_text or len(message_text.strip()) < 10:
            return []

        try:
            preferences = self._extract_preferences(caregiver_id, caregiver_name, message_text)
            if not preferences:
                return []

            memory_ids = []
            for pref in preferences:
                memory_id = self._store_preference(caregiver_id, caregiver_name, pref)
                if memory_id:
                    memory_ids.append(memory_id)

            return memory_ids

        except Exception as e:
            logger.warning(f"Preference extraction failed for {caregiver_name}: {e}")
            return []

    def _extract_preferences(
        self,
        caregiver_id: str,
        caregiver_name: str,
        message_text: str
    ) -> List[Dict[str, Any]]:
        """Use configured LLM provider to extract structured preferences from text."""
        try:
            prompt = EXTRACTION_PROMPT.format(
                name=caregiver_name,
                caregiver_id=caregiver_id,
                message=message_text
            )

            if self.llm_provider == "gemini" and self.gemini_client:
                model = os.getenv("GIGI_LLM_MODEL", "gemini-2.5-flash")
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        max_output_tokens=500,
                        temperature=0.1,
                    ),
                )
                result_text = response.text.strip()
            else:
                response = self.anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                result_text = response.content[0].text.strip()

            # Parse JSON - handle potential markdown wrapping
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            data = json.loads(result_text)
            return data.get("preferences", [])

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse preference extraction result: {e}")
            return []
        except Exception as e:
            logger.warning(f"Preference extraction error ({self.llm_provider}): {e}")
            return []

    def _store_preference(
        self,
        caregiver_id: str,
        caregiver_name: str,
        pref: Dict[str, Any]
    ) -> Optional[str]:
        """Store a single preference in gigi_memories, or reinforce if exists."""
        from gigi.memory_system import MemoryType, MemorySource, ImpactLevel

        pref_type = pref.get("type", "general")
        content = pref.get("content", "")
        hard = pref.get("hard_constraint", False)

        if not content:
            return None

        # Build metadata
        metadata = {
            "caregiver_id": caregiver_id,
            "caregiver_name": caregiver_name,
            "preference_type": pref_type,
            "hard_constraint": hard,
        }

        # Include structured fields if present
        for field in ["day_of_week", "time_preference", "client_name", "location"]:
            if pref.get(field):
                metadata[field] = pref[field]

        # Check for existing similar preference
        existing = self._find_similar_preference(caregiver_id, content, pref_type)
        if existing:
            self.memory.reinforce_memory(existing.id)
            logger.info(f"Reinforced preference for {caregiver_name}: {content}")
            return existing.id

        # Create new memory
        impact = ImpactLevel.MEDIUM if hard else ImpactLevel.LOW
        memory_type = MemoryType.INFERRED_PATTERN  # Start at 0.5-0.7 confidence

        memory_id = self.memory.create_memory(
            content=f"Caregiver {caregiver_name}: {content}",
            memory_type=memory_type,
            source=MemorySource.INFERENCE,
            confidence=0.6 if hard else 0.5,
            category="caregiver_preference",
            impact_level=impact,
            metadata=metadata
        )

        logger.info(f"New preference for {caregiver_name}: {content} (hard={hard})")
        return memory_id

    def _find_similar_preference(
        self,
        caregiver_id: str,
        content: str,
        pref_type: str
    ) -> Optional[Any]:
        """Find an existing preference that matches this one."""
        from gigi.memory_system import MemoryStatus

        existing = self.memory.query_memories(
            category="caregiver_preference",
            status=MemoryStatus.ACTIVE,
            min_confidence=0.0,
            limit=100
        )

        content_lower = content.lower()
        for mem in existing:
            meta = mem.metadata or {}
            if meta.get("caregiver_id") != caregiver_id:
                continue
            if meta.get("preference_type") != pref_type:
                continue
            # Simple similarity check - same key words
            mem_content_lower = mem.content.lower()
            if content_lower in mem_content_lower or mem_content_lower in f"caregiver: {content_lower}":
                return mem

        return None

    def get_caregiver_preferences(
        self,
        caregiver_id: str,
        preference_type: Optional[str] = None
    ) -> List[Any]:
        """Get all active preferences for a caregiver."""
        from gigi.memory_system import MemoryStatus

        all_prefs = self.memory.query_memories(
            category="caregiver_preference",
            status=MemoryStatus.ACTIVE,
            min_confidence=0.3,
            limit=200
        )

        result = []
        for mem in all_prefs:
            meta = mem.metadata or {}
            if meta.get("caregiver_id") != caregiver_id:
                continue
            if preference_type and meta.get("preference_type") != preference_type:
                continue
            result.append(mem)

        return result

    def get_hard_constraints(self, caregiver_id: str) -> List[Any]:
        """Get only hard constraints (high confidence, hard_constraint=true)."""
        prefs = self.get_caregiver_preferences(caregiver_id)
        return [p for p in prefs
                if p.metadata.get("hard_constraint", False)
                and p.confidence >= 0.5]

    def get_soft_preferences(self, caregiver_id: str) -> List[Any]:
        """Get soft preferences (not hard constraints)."""
        prefs = self.get_caregiver_preferences(caregiver_id)
        return [p for p in prefs
                if not p.metadata.get("hard_constraint", False)]
