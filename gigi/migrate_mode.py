#!/usr/bin/env python3
"""
Migration script to create Gigi mode detection tables in production database.

Usage:
    python migrate_mode.py
"""

import os
import sys

def run_migration():
    """Run migration to create mode tables."""
    print("=" * 60)
    print("GIGI MODE DETECTION SYSTEM MIGRATION")
    print("=" * 60)
    print(f"\nInitializing mode detector...")

    try:
        from gigi.mode_detector import ModeDetector

        detector = ModeDetector()
        print("✓ Mode tables created successfully!")

        # Test mode detection
        print("\nTesting mode detection...")
        current = detector.get_current_mode()

        print(f"\nCurrent Mode:")
        print(f"  Mode: {current.mode.value}")
        print(f"  Source: {current.source.value}")
        print(f"  Confidence: {current.confidence:.2f}")
        print(f"  Reason: {current.context.get('reason', 'N/A')}")

        # Show behavior config
        config = detector.get_mode_behavior_config(current.mode)
        print(f"\nBehavior Configuration:")
        print(f"  Interrupt threshold: {config['interrupt_threshold']}")
        print(f"  Response style: {config['response_style']}")
        print(f"  Tone: {config['tone']}")

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
