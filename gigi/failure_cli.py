#!/usr/bin/env python3
"""
Gigi Failure Management CLI

View and manage failure logs, detect patterns, resolve issues.

Usage:
    python failure_cli.py recent                    # Show recent failures
    python failure_cli.py recent --severity critical # Filter by severity
    python failure_cli.py stats --days 7             # Show failure statistics
    python failure_cli.py resolve <failure_id> "Fixed by..."
    python failure_cli.py meltdown                   # Check for meltdown state
"""

import argparse
import sys
from datetime import datetime
from failure_handler import FailureHandler, FailureType, FailureSeverity, FailureAction


def format_failure(failure):
    """Format a single failure for display."""
    print(f"\n{'='*60}")
    print(f"Failure ID: {failure.id}")
    print(f"Type:       {failure.type.value}")
    print(f"Severity:   {failure.severity.value.upper()}")
    print(f"Action:     {failure.action_taken.value}")
    print(f"Occurred:   {failure.occurred_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if failure.tool_name:
        print(f"Tool:       {failure.tool_name}")
    if failure.confidence is not None:
        print(f"Confidence: {failure.confidence:.2f}")
    print(f"Message:    {failure.message}")
    if failure.context:
        print(f"Context:")
        for key, value in failure.context.items():
            print(f"  {key}: {value}")
    if failure.resolved:
        print(f"RESOLVED:   {failure.resolution}")
        print(f"            (resolved at {failure.resolved_at})")
    else:
        print(f"Status:     UNRESOLVED")
    print(f"{'='*60}")


def cmd_recent(args):
    """Show recent failures."""
    handler = FailureHandler()

    severity = None
    if args.severity:
        try:
            severity = FailureSeverity(args.severity.lower())
        except ValueError:
            print(f"Error: Invalid severity '{args.severity}'")
            print(f"Valid: info, warning, error, critical")
            sys.exit(1)

    failures = handler.get_recent_failures(hours=args.hours, severity=severity)

    if not failures:
        print(f"\n✓ No failures in the last {args.hours} hours")
        if severity:
            print(f"  (filtered by severity: {severity.value})")
        print()
        return

    print(f"\n{'='*60}")
    print(f"Recent Failures (Last {args.hours} hours)")
    if severity:
        print(f"Filtered by severity: {severity.value.upper()}")
    print(f"{'='*60}")

    for i, failure in enumerate(failures, 1):
        print(f"\n{i}. [{failure.severity.value.upper()}] {failure.type.value}")
        print(f"   {failure.occurred_at.strftime('%Y-%m-%d %H:%M:%S')} - {failure.message}")
        if failure.tool_name:
            print(f"   Tool: {failure.tool_name}")
        print(f"   Action: {failure.action_taken.value}")
        if failure.resolved:
            print(f"   ✓ RESOLVED: {failure.resolution}")
        else:
            print(f"   ⚠ UNRESOLVED (ID: {failure.id})")

    print(f"\n{'='*60}")
    print(f"Total: {len(failures)} failure(s)")
    print(f"{'='*60}\n")


def cmd_detail(args):
    """Show detailed info for a specific failure."""
    handler = FailureHandler()

    # This would require a get_failure_by_id method
    print("Not implemented yet - use 'recent' to see all failures")


def cmd_stats(args):
    """Show failure statistics."""
    handler = FailureHandler()
    stats = handler.get_failure_stats(days=args.days)

    print(f"\n{'='*60}")
    print(f"Failure Statistics (Last {args.days} days)")
    print(f"{'='*60}\n")

    print(f"Total Failures: {stats['total_failures']}")

    if stats['by_severity']:
        print(f"\nBy Severity:")
        for severity, count in sorted(stats['by_severity'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {severity:<12} {count:>5}")

    if stats['by_type']:
        print(f"\nBy Type:")
        for ftype, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {ftype:<30} {count:>5}")

    print(f"\n{'='*60}\n")


def cmd_resolve(args):
    """Resolve a failure."""
    handler = FailureHandler()

    try:
        handler.resolve_failure(args.failure_id, args.resolution)
        print(f"\n✓ Failure {args.failure_id} marked as resolved")
        print(f"  Resolution: {args.resolution}\n")
    except Exception as e:
        print(f"\n✗ Error resolving failure: {e}\n")
        sys.exit(1)


def cmd_meltdown(args):
    """Check for meltdown state."""
    handler = FailureHandler()

    # Check recent critical failures
    recent_critical = handler.get_recent_failures(hours=1, severity=FailureSeverity.CRITICAL)
    recent_errors = handler.get_recent_failures(hours=1, severity=FailureSeverity.ERROR)

    is_meltdown = handler.detect_meltdown()

    print(f"\n{'='*60}")
    print("Meltdown Detection")
    print(f"{'='*60}\n")

    if is_meltdown:
        print("⚠️  MELTDOWN DETECTED")
        print(f"   {len(handler.recent_failures)} failures in {handler.meltdown_window.seconds/60:.0f} minutes")
        print(f"   Threshold: {handler.meltdown_threshold} failures")
        print("\n   RECOMMENDATION: Stop automatic operations until issues are resolved")
    else:
        print("✓ No meltdown detected")
        print(f"  Recent failures: {len(handler.recent_failures)}")
        print(f"  Threshold: {handler.meltdown_threshold} failures in {handler.meltdown_window.seconds/60:.0f} minutes")

    print(f"\nLast hour:")
    print(f"  Critical failures: {len(recent_critical)}")
    print(f"  Error failures:    {len(recent_errors)}")

    if recent_critical:
        print(f"\n  Recent critical failures:")
        for f in recent_critical[:5]:
            print(f"    - {f.occurred_at.strftime('%H:%M:%S')} - {f.message}")

    print(f"\n{'='*60}\n")


def cmd_test(args):
    """Test the failure handler."""
    handler = FailureHandler()

    print("\n" + "="*60)
    print("Testing Failure Handler")
    print("="*60)

    # Test 1: Tool failure
    print("\n1. Simulating tool failure...")
    action, msg = handler.handle_tool_failure(
        tool_name="wellsky",
        error=ConnectionError("Connection timeout"),
        context={"endpoint": "/api/shifts"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Test 2: Low confidence
    print("\n2. Simulating low confidence...")
    action, msg = handler.handle_low_confidence(
        action="send emergency SMS",
        confidence=0.45,
        context={"situation": "unclear if emergency"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Test 3: Conflicting instructions
    print("\n3. Simulating conflicting instructions...")
    action, msg = handler.handle_conflicting_instructions(
        instruction1="Never send SMS after 9pm",
        instruction2="Always send emergency alerts immediately",
        context={"time": "10:30 PM", "type": "emergency"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    # Test 4: Missing context
    print("\n4. Simulating missing context...")
    action, msg = handler.handle_missing_context(
        action="book flight",
        missing_info=["destination", "travel dates", "budget"],
        context={"user_request": "book me a flight"}
    )
    print(f"   Action: {action.value}")
    print(f"   Message: {msg}")

    print("\n" + "="*60)
    print("Test failures logged. Run 'python failure_cli.py recent' to see them.")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Gigi Failure Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Recent failures
    recent_parser = subparsers.add_parser('recent', help='Show recent failures')
    recent_parser.add_argument('--hours', type=int, default=24, help='Hours to look back (default: 24)')
    recent_parser.add_argument('--severity', help='Filter by severity (info, warning, error, critical)')

    # Failure details
    detail_parser = subparsers.add_parser('detail', help='Show detailed failure info')
    detail_parser.add_argument('failure_id', help='Failure ID')

    # Statistics
    stats_parser = subparsers.add_parser('stats', help='Show failure statistics')
    stats_parser.add_argument('--days', type=int, default=7, help='Days to analyze (default: 7)')

    # Resolve failure
    resolve_parser = subparsers.add_parser('resolve', help='Mark failure as resolved')
    resolve_parser.add_argument('failure_id', help='Failure ID')
    resolve_parser.add_argument('resolution', help='Resolution description')

    # Meltdown check
    subparsers.add_parser('meltdown', help='Check for meltdown state')

    # Test
    subparsers.add_parser('test', help='Test the failure handler')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handler
    commands = {
        'recent': cmd_recent,
        'detail': cmd_detail,
        'stats': cmd_stats,
        'resolve': cmd_resolve,
        'meltdown': cmd_meltdown,
        'test': cmd_test
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
