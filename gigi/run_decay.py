#!/usr/bin/env python3
"""
Daily memory decay process - Run this via Mac Mini (Local) Scheduler

Usage:
    python run_decay.py
"""

import logging
from memory_system import MemorySystem

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run daily memory decay process."""
    logger.info("=" * 60)
    logger.info("GIGI MEMORY DECAY PROCESS")
    logger.info("=" * 60)

    try:
        memory_system = MemorySystem()
        logger.info("✓ Memory system initialized")

        # Run decay
        logger.info("Running decay on all memories...")
        memory_system.decay_memories()
        logger.info("✓ Decay process completed successfully")

        # Cleanup
        logger.info("Completed at: " + str(datetime.now()))

    except Exception as e:
        logger.error(f"✗ Decay process failed: {e}")
        raise


if __name__ == "__main__":
    from datetime import datetime
    main()
