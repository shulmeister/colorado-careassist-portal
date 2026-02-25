#!/usr/bin/env python3
"""
Migration script to create Gigi failure protocol tables in production database.

Usage:
    python migrate_failure.py
"""

import os
import sys

def run_migration():
    """Run migration to create failure tables."""
    print("=" * 60)
    print("GIGI FAILURE PROTOCOL SYSTEM MIGRATION")
    print("=" * 60)
    print(f"\nInitializing failure handler...")

    try:
        from gigi.failure_handler import FailureHandler, FailureType, FailureSeverity, FailureAction

        handler = FailureHandler()
        print("✓ Failure tables created successfully!")

        # Run a test
        print("\nRunning test failure...")
        test_id = handler.log_failure(
            failure_type=FailureType.TOOL_FAILURE,
            message="Migration test - database connection successful",
            severity=FailureSeverity.INFO,
            action=FailureAction.CONTINUE,
            context={"test": True, "migration": "v1"}
        )

        print(f"✓ Test failure logged: {test_id}")

        # Get stats
        stats = handler.get_failure_stats(days=1)
        print(f"\nCurrent stats:")
        print(f"  Total failures: {stats['total_failures']}")

        # Resolve the test failure
        handler.resolve_failure(test_id, "Migration test completed successfully")
        print(f"✓ Test failure resolved")

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print("\nFailure Protocol System is ready:")
        print("  - Tool failure detection")
        print("  - Low confidence handling")
        print("  - Conflict detection")
        print("  - Meltdown prevention")
        print("  - Failure logging and stats")
        print("\nUse 'python gigi/failure_cli.py' to manage failures")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
