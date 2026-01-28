#!/usr/bin/env python3
"""
Gigi Mode Management CLI

Manage operating modes for Gigi.

Usage:
    python mode_cli.py current                          # Show current mode
    python mode_cli.py set focus                        # Set mode to focus
    python mode_cli.py set travel --expires 2024-01-30  # Set with expiration
    python mode_cli.py history --days 7                 # Show mode history
    python mode_cli.py stats --days 30                  # Show mode statistics
    python mode_cli.py config focus                     # Show mode behavior config
"""

import argparse
import sys
from datetime import datetime
from mode_detector import ModeDetector, OperatingMode, ModeSource, parse_mode_command


def format_mode_info(mode_info):
    """Format mode info for display."""
    print(f"\n{'='*60}")
    print(f"Current Mode: {mode_info.mode.value.upper()}")
    print(f"{'='*60}")
    print(f"Source:      {mode_info.source.value}")
    print(f"Confidence:  {mode_info.confidence:.2f}")
    print(f"Set at:      {mode_info.set_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if mode_info.expires_at:
        print(f"Expires at:  {mode_info.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"Expires at:  Never")

    if mode_info.context:
        print(f"\nContext:")
        for key, value in mode_info.context.items():
            print(f"  {key}: {value}")
    print(f"{'='*60}\n")


def cmd_current(args):
    """Show current mode."""
    detector = ModeDetector()
    mode_info = detector.get_current_mode()
    format_mode_info(mode_info)

    # Show behavior config
    config = detector.get_mode_behavior_config(mode_info.mode)
    print("\nBehavior Configuration:")
    print(f"  Interrupt threshold:  {config['interrupt_threshold']}")
    print(f"  Response style:       {config['response_style']}")
    print(f"  Response delay:       {config['response_delay']}")
    print(f"  Tone:                 {config['tone']}")
    print(f"  Auto actions:         {', '.join(config['auto_actions'])}")
    print(f"  Escalation rules:     {config['escalation_rules']}\n")


def cmd_set(args):
    """Set operating mode."""
    detector = ModeDetector()

    try:
        mode = OperatingMode(args.mode.lower())
    except ValueError:
        print(f"Error: Invalid mode '{args.mode}'")
        print(f"Valid modes: {', '.join([m.value for m in OperatingMode])}")
        sys.exit(1)

    expires_at = None
    if args.expires:
        try:
            expires_at = datetime.fromisoformat(args.expires)
        except ValueError:
            print(f"Error: Invalid date format '{args.expires}'. Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD")
            sys.exit(1)

    context = {}
    if args.reason:
        context['reason'] = args.reason

    detector.set_mode(
        mode=mode,
        source=ModeSource.EXPLICIT,
        confidence=1.0,
        expires_at=expires_at,
        context=context
    )

    print(f"\n✓ Mode set to {mode.value}")
    if expires_at:
        print(f"  Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if args.reason:
        print(f"  Reason: {args.reason}")
    print()


def cmd_history(args):
    """Show mode history."""
    detector = ModeDetector()
    history = detector.get_mode_history(days=args.days)

    print(f"\n{'='*60}")
    print(f"Mode History (Last {args.days} days)")
    print(f"{'='*60}\n")

    if not history:
        print("No mode history found.\n")
        return

    for entry in history:
        started = entry['started_at'].strftime('%Y-%m-%d %H:%M')
        ended = entry['ended_at'].strftime('%H:%M') if entry['ended_at'] else 'ongoing'
        duration = f"{entry['duration_minutes']:.0f}m" if entry['duration_minutes'] else '-'

        print(f"{entry['mode']:12} | {started} - {ended:10} | {duration:8} | {entry['source']}")

    print()


def cmd_stats(args):
    """Show mode statistics."""
    detector = ModeDetector()
    stats = detector.get_mode_stats(days=args.days)

    print(f"\n{'='*60}")
    print(f"Mode Statistics (Last {args.days} days)")
    print(f"{'='*60}\n")

    # Show current mode first
    if 'current' in stats:
        current = stats.pop('current')
        print(f"Current Mode: {current['mode'].upper()}")
        print(f"  Source: {current['source']}")
        print(f"  Confidence: {current['confidence']:.2f}")
        print(f"  Set at: {current['set_at']}\n")

    if not stats:
        print("No mode history available.\n")
        return

    print(f"{'Mode':<12} {'Count':>8} {'Total Hours':>12} {'Avg Duration':>14} {'Avg Confidence':>16}")
    print(f"{'-'*12} {'-'*8} {'-'*12} {'-'*14} {'-'*16}")

    for mode, data in stats.items():
        total_hours = data['total_minutes'] / 60 if data['total_minutes'] else 0
        avg_duration = f"{data['avg_duration']:.0f}m" if data['avg_duration'] else '-'

        print(f"{mode:<12} {data['occurrences']:>8} {total_hours:>11.1f}h {avg_duration:>14} {data['avg_confidence']:>15.2f}")

    print()


def cmd_config(args):
    """Show behavior configuration for a mode."""
    detector = ModeDetector()

    try:
        mode = OperatingMode(args.mode.lower())
    except ValueError:
        print(f"Error: Invalid mode '{args.mode}'")
        print(f"Valid modes: {', '.join([m.value for m in OperatingMode])}")
        sys.exit(1)

    config = detector.get_mode_behavior_config(mode)

    print(f"\n{'='*60}")
    print(f"{mode.value.upper()} Mode Behavior Configuration")
    print(f"{'='*60}\n")

    print(f"Interrupt Threshold:  {config['interrupt_threshold']}")
    print(f"Response Style:       {config['response_style']}")
    print(f"Response Delay:       {config['response_delay']}")
    print(f"Tone:                 {config['tone']}")
    print(f"Escalation Rules:     {config['escalation_rules']}")

    print(f"\nAuto Actions:")
    for action in config['auto_actions']:
        print(f"  - {action}")

    print()


def cmd_parse(args):
    """Parse mode command from natural language."""
    result = parse_mode_command(args.text)

    if result:
        mode, expires = result
        print(f"\nDetected Mode: {mode.value}")
        if expires:
            print(f"Expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    else:
        print("\nNo mode command detected.\n")


def main():
    parser = argparse.ArgumentParser(
        description='Gigi Mode Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Current mode
    subparsers.add_parser('current', help='Show current mode')

    # Set mode
    set_parser = subparsers.add_parser('set', help='Set operating mode')
    set_parser.add_argument('mode', help='Mode to set (focus, execution, decision, travel, off_grid, crisis, thinking, review)')
    set_parser.add_argument('--expires', help='Expiration date/time (YYYY-MM-DD HH:MM:SS)')
    set_parser.add_argument('--reason', help='Reason for mode change')

    # History
    history_parser = subparsers.add_parser('history', help='Show mode history')
    history_parser.add_argument('--days', type=int, default=7, help='Number of days to show (default: 7)')

    # Stats
    stats_parser = subparsers.add_parser('stats', help='Show mode statistics')
    stats_parser.add_argument('--days', type=int, default=30, help='Number of days to analyze (default: 30)')

    # Config
    config_parser = subparsers.add_parser('config', help='Show mode behavior configuration')
    config_parser.add_argument('mode', help='Mode to show config for')

    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse mode command from natural language')
    parse_parser.add_argument('text', help='Text to parse')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to command handler
    commands = {
        'current': cmd_current,
        'set': cmd_set,
        'history': cmd_history,
        'stats': cmd_stats,
        'config': cmd_config,
        'parse': cmd_parse
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
