#!/usr/bin/env python3
"""
Gigi Memory Decay — Daily cron job

Runs decay_memories() on all active memories, reducing confidence
based on memory type decay rates. Should run daily at 3 AM.

Memory types and decay rates:
- EXPLICIT_INSTRUCTION: never decays
- CORRECTION: 5% per month
- CONFIRMED_PATTERN: 10% per month
- INFERRED_PATTERN: 20% per month
- SINGLE_INFERENCE: 30% per month
- TEMPORARY: 50% per day (archives after 48hrs)
"""

import logging
import os
import sys

# Load env vars
env_path = os.path.expanduser("~/.gigi-env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if not key.startswith("export "):
                    os.environ.setdefault(key.strip(), value.strip())

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gigi-memory-decay")

def main():
    from gigi.memory_system import MemorySystem
    ms = MemorySystem()

    # Count before
    before = ms.query_memories(min_confidence=0.0, limit=1000)
    logger.info(f"Running memory decay on {len(before)} active memories")

    ms.decay_memories()

    # Count after
    after = ms.query_memories(min_confidence=0.0, limit=1000)
    archived = len(before) - len(after)
    if archived > 0:
        logger.info(f"Archived {archived} memories below threshold")
    logger.info(f"Memory decay complete. {len(after)} active memories remain.")

    # Prune old conversations (>7 days, summarizes before deleting)
    try:
        from gigi.conversation_store import ConversationStore
        cs = ConversationStore()
        pruned = cs.prune_old(max_age_hours=168)
        logger.info(f"Conversation prune: removed {pruned} messages older than 168h (7 days)")
    except Exception as e:
        logger.warning(f"Conversation prune failed: {e}")

if __name__ == "__main__":
    main()
