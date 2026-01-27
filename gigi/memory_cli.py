#!/usr/bin/env python3
"""
Gigi Memory CLI - Manage and inspect Gigi's memory system

Usage:
    python memory_cli.py create "Never book United" --type explicit --category travel
    python memory_cli.py list --category travel
    python memory_cli.py reinforce <memory_id>
    python memory_cli.py decay  # Run decay process
    python memory_cli.py audit <memory_id>
"""

import argparse
from memory_system import (
    MemorySystem,
    MemoryType,
    MemorySource,
    MemoryStatus,
    ImpactLevel
)


def main():
    parser = argparse.ArgumentParser(description="Manage Gigi's memory system")
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Create memory
    create_parser = subparsers.add_parser('create', help='Create a new memory')
    create_parser.add_argument('content', help='Memory content')
    create_parser.add_argument('--type', required=True, choices=[
        'explicit', 'correction', 'confirmed', 'inferred', 'single', 'temporary'
    ])
    create_parser.add_argument('--category', required=True, help='Category (travel, communication, etc.)')
    create_parser.add_argument('--impact', default='medium', choices=['high', 'medium', 'low'])
    create_parser.add_argument('--confidence', type=float, help='Confidence override')

    # List memories
    list_parser = subparsers.add_parser('list', help='List memories')
    list_parser.add_argument('--category', help='Filter by category')
    list_parser.add_argument('--status', choices=['active', 'inactive', 'archived'])
    list_parser.add_argument('--min-confidence', type=float, default=0.0)
    list_parser.add_argument('--limit', type=int, default=50)

    # Get memory
    get_parser = subparsers.add_parser('get', help='Get specific memory')
    get_parser.add_argument('memory_id', help='Memory ID')

    # Reinforce memory
    reinforce_parser = subparsers.add_parser('reinforce', help='Reinforce a memory')
    reinforce_parser.add_argument('memory_id', help='Memory ID')

    # Run decay
    decay_parser = subparsers.add_parser('decay', help='Run decay process on all memories')

    # Audit log
    audit_parser = subparsers.add_parser('audit', help='View audit log for memory')
    audit_parser.add_argument('memory_id', help='Memory ID')
    audit_parser.add_argument('--limit', type=int, default=20)

    # Conflicts
    conflicts_parser = subparsers.add_parser('conflicts', help='Detect conflicts for content')
    conflicts_parser.add_argument('content', help='New memory content to check')
    conflicts_parser.add_argument('--category', required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    memory_system = MemorySystem()

    if args.command == 'create':
        # Map string to enum
        type_map = {
            'explicit': MemoryType.EXPLICIT_INSTRUCTION,
            'correction': MemoryType.CORRECTION,
            'confirmed': MemoryType.CONFIRMED_PATTERN,
            'inferred': MemoryType.INFERRED_PATTERN,
            'single': MemoryType.SINGLE_INFERENCE,
            'temporary': MemoryType.TEMPORARY
        }

        impact_map = {
            'high': ImpactLevel.HIGH,
            'medium': ImpactLevel.MEDIUM,
            'low': ImpactLevel.LOW
        }

        # Determine source from type
        source = MemorySource.EXPLICIT if args.type == 'explicit' else MemorySource.INFERENCE

        # Default confidence based on type
        confidence = args.confidence if args.confidence else {
            'explicit': 1.0,
            'correction': 0.9,
            'confirmed': 0.8,
            'inferred': 0.6,
            'single': 0.4,
            'temporary': 0.5
        }[args.type]

        memory_id = memory_system.create_memory(
            content=args.content,
            memory_type=type_map[args.type],
            source=source,
            confidence=confidence,
            category=args.category,
            impact_level=impact_map[args.impact]
        )

        print(f"✓ Created memory: {memory_id}")
        print(f"  Content: {args.content}")
        print(f"  Type: {args.type}")
        print(f"  Confidence: {confidence}")

    elif args.command == 'list':
        status = MemoryStatus(args.status) if args.status else None
        memories = memory_system.query_memories(
            category=args.category,
            status=status,
            min_confidence=args.min_confidence,
            limit=args.limit
        )

        if not memories:
            print("No memories found")
            return

        print(f"\nFound {len(memories)} memories:\n")
        for memory in memories:
            status_icon = {
                MemoryStatus.ACTIVE: "●",
                MemoryStatus.INACTIVE: "○",
                MemoryStatus.ARCHIVED: "✕"
            }.get(memory.status, "?")

            print(f"{status_icon} [{memory.type.value}] {memory.content}")
            print(f"   ID: {memory.id}")
            print(f"   Confidence: {memory.confidence:.2f} | Category: {memory.category} | Impact: {memory.impact_level.value}")
            print(f"   Created: {memory.created_at.strftime('%Y-%m-%d %H:%M')}")
            if memory.last_reinforced_at:
                print(f"   Last reinforced: {memory.last_reinforced_at.strftime('%Y-%m-%d %H:%M')} ({memory.reinforcement_count} times)")
            print()

    elif args.command == 'get':
        memory = memory_system.get_memory(args.memory_id)
        if not memory:
            print(f"Memory {args.memory_id} not found")
            return

        print(f"\nMemory: {memory.id}")
        print(f"Type: {memory.type.value}")
        print(f"Content: {memory.content}")
        print(f"Confidence: {memory.confidence:.2f}")
        print(f"Status: {memory.status.value}")
        print(f"Category: {memory.category}")
        print(f"Impact: {memory.impact_level.value}")
        print(f"Source: {memory.source.value}")
        print(f"Created: {memory.created_at}")
        if memory.last_confirmed_at:
            print(f"Last confirmed: {memory.last_confirmed_at}")
        if memory.last_reinforced_at:
            print(f"Last reinforced: {memory.last_reinforced_at} ({memory.reinforcement_count} times)")
        if memory.conflicts_with:
            print(f"Conflicts with: {', '.join(memory.conflicts_with)}")

    elif args.command == 'reinforce':
        success = memory_system.reinforce_memory(args.memory_id)
        if success:
            memory = memory_system.get_memory(args.memory_id)
            print(f"✓ Reinforced memory")
            print(f"  New confidence: {memory.confidence:.2f}")
            print(f"  Reinforcement count: {memory.reinforcement_count}")
        else:
            print(f"✗ Failed to reinforce memory {args.memory_id}")

    elif args.command == 'decay':
        print("Running decay process...")
        memory_system.decay_memories()
        print("✓ Decay completed")

    elif args.command == 'audit':
        log_entries = memory_system.get_audit_log(args.memory_id, limit=args.limit)

        if not log_entries:
            print(f"No audit log for memory {args.memory_id}")
            return

        print(f"\nAudit log for memory {args.memory_id}:\n")
        for entry in log_entries:
            timestamp = entry['created_at'].strftime('%Y-%m-%d %H:%M:%S')
            event = entry['event_type']
            reason = entry['reason']

            print(f"[{timestamp}] {event}")
            if entry['old_confidence'] is not None:
                print(f"  Confidence: {entry['old_confidence']:.2f} → {entry['new_confidence']:.2f}")
            print(f"  {reason}")
            print()

    elif args.command == 'conflicts':
        conflicts = memory_system.detect_conflicts(args.content, args.category)

        if not conflicts:
            print("✓ No conflicts detected")
            return

        print(f"\n⚠ Found {len(conflicts)} potential conflicts:\n")
        for memory in conflicts:
            print(f"- {memory.content}")
            print(f"  ID: {memory.id} | Confidence: {memory.confidence:.2f}")
            print()


if __name__ == "__main__":
    main()
