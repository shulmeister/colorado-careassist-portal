"""
Entity Resolution Service for Gigi

This service resolves ambiguous names mentioned in conversation into specific
WellSky client or caregiver IDs. It acts as Gigi's "short-term memory" and
reasoning layer, enabling more natural conversation.

Example:
- Caregiver Dina says: "I can't make my shift with Preston."
- resolve_person(name="Preston", context={"caregiver_id": dina.id})
  - -> Searches Dina's upcoming shifts for a client named "Preston".
  - -> Returns Preston's full ID and profile.
"""

import logging
from typing import Optional, Dict, Any, List

# Use a forward reference for WellSkyService to avoid circular import issues
# if this service grows and is imported by wellsky_service.
from services.wellsky_service import WellSkyService

logger = logging.getLogger(__name__)

class EntityResolutionService:
    def __init__(self, wellsky_service: WellSkyService):
        self.ws = wellsky_service

    def resolve_person(
        self,
        name: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Resolves a person's name to a specific client or caregiver ID.

        Args:
            name: The first name or full name to resolve.
            context: The conversational context, e.g., {"caregiver_id": "123"}

        Returns:
            A dict with resolution status, type, id, and name, or ambiguity info.
        """
        name_lower = name.lower()
        
        # 1. Contextual Search (Highest Priority)
        if context and context.get("caregiver_id"):
            try:
                shifts = self.ws.get_shifts(caregiver_id=context["caregiver_id"], limit=10)
                for shift in shifts:
                    if name_lower in shift.client_name.lower():
                        logger.info(f"Resolved '{name}' to client '{shift.client_name}' via caregiver context.")
                        return {
                            "status": "resolved",
                            "type": "client",
                            "id": shift.client_id,
                            "name": shift.client_name,
                            "source": "caregiver_schedule"
                        }
            except Exception as e:
                logger.warning(f"Contextual shift search failed: {e}")

        # 2. General Search (Fallback)
        try:
            # Search both clients and caregivers
            clients = self.ws.search_patients(first_name=name)
            caregivers = self.ws.search_practitioners(first_name=name)
            
            all_matches: List[Dict[str, Any]] = []
            for c in clients:
                all_matches.append({"type": "client", "id": c.id, "name": c.full_name})
            for cg in caregivers:
                all_matches.append({"type": "caregiver", "id": cg.id, "name": cg.full_name})

            # 3. Disambiguation
            if len(all_matches) == 1:
                match = all_matches[0]
                logger.info(f"Resolved '{name}' to unique {match['type']} '{match['name']}'.")
                return {
                    "status": "resolved",
                    "type": match['type'],
                    "id": match['id'],
                    "name": match['name'],
                    "source": "unique_db_match"
                }
            elif len(all_matches) > 1:
                logger.warning(f"Ambiguous name '{name}': Found {len(all_matches)} matches.")
                return {
                    "status": "ambiguous",
                    "message": f"I found multiple people named {name}. Can you provide a last name or more detail?",
                    "options": [f"{m['name']} ({m['type']})" for m in all_matches]
                }
            else:
                logger.info(f"Could not resolve '{name}' to any known person.")
                return {
                    "status": "not_found",
                    "message": f"I don't have a record for anyone named {name}. Could you please spell out the name for me?",
                }
        except Exception as e:
            logger.error(f"Error during general entity resolution: {e}")
            return {
                "status": "error",
                "message": "I'm having trouble accessing records right now. Please try again in a moment.",
            }

# Singleton instance for use in Gigi's tools
# This avoids re-initializing the WellSkyService every time
try:
    # This assumes wellsky_service is a singleton instance available for import
    from services.wellsky_service import wellsky_service
    entity_resolver = EntityResolutionService(wellsky_service=wellsky_service)
    logger.info("✓ Entity Resolution Service initialized.")
except ImportError:
    entity_resolver = None
    logger.warning("Entity Resolution Service could not be initialized.")
