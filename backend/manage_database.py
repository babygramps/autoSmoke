#!/usr/bin/env python3
"""Database management CLI tool.

Provides commands for maintaining and optimizing the database.
"""

import sys
import argparse
import logging
from core.data_cleanup import cleanup_manager
from core.db_maintenance import db_maintenance

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_stats():
    """Show database statistics."""
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    
    # Get data stats
    stats = cleanup_manager.get_database_stats()
    print("\nData Counts:")
    print(f"  Readings:              {stats['readings']:,}")
    print(f"  Thermocouple Readings: {stats['thermocouple_readings']:,}")
    print(f"  Events:                {stats['events']:,}")
    print(f"  Alerts:                {stats['alerts']:,}")
    print(f"  Smoke Sessions:        {stats['smoke_sessions']:,}")
    
    if stats['oldest_reading'] and stats['newest_reading']:
        print(f"\nData Time Range:")
        print(f"  Oldest: {stats['oldest_reading']}")
        print(f"  Newest: {stats['newest_reading']}")
    
    # Get database info
    db_info = db_maintenance.get_database_info()
    if db_info:
        print(f"\nDatabase Size:")
        print(f"  Total:         {db_info['total_size_mb']} MB")
        print(f"  Used:          {db_info['used_size_mb']} MB")
        print(f"  Free:          {db_info['free_size_mb']} MB")
        print(f"  Fragmentation: {db_info['fragmentation_pct']}%")
        print(f"\nDatabase Mode:")
        print(f"  Journal Mode:  {db_info['journal_mode']}")
        print(f"  Page Size:     {db_info['page_size']} bytes")
        print(f"  Page Count:    {db_info['page_count']:,}")
    
    print("=" * 60 + "\n")


def cmd_cleanup(args):
    """Run data cleanup."""
    print("\n" + "=" * 60)
    print("DATA CLEANUP")
    print("=" * 60)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No data will be deleted")
    
    stats = cleanup_manager.cleanup_old_data(
        reading_days=args.reading_days,
        event_days=args.event_days,
        alert_days=args.alert_days,
        dry_run=args.dry_run
    )
    
    if not args.dry_run and (stats['readings_deleted'] > 0 or stats['events_deleted'] > 0):
        print("\nRunning VACUUM to reclaim space...")
        db_maintenance.vacuum()
    
    print("=" * 60 + "\n")


def cmd_vacuum():
    """Run VACUUM on database."""
    print("\n" + "=" * 60)
    print("DATABASE VACUUM")
    print("=" * 60)
    
    success = db_maintenance.vacuum()
    
    if success:
        print("\n✅ VACUUM completed successfully")
    else:
        print("\n❌ VACUUM failed")
    
    print("=" * 60 + "\n")


def cmd_analyze():
    """Run ANALYZE on database."""
    print("\n" + "=" * 60)
    print("DATABASE ANALYZE")
    print("=" * 60)
    
    success = db_maintenance.analyze()
    
    if success:
        print("\n✅ ANALYZE completed successfully")
    else:
        print("\n❌ ANALYZE failed")
    
    print("=" * 60 + "\n")


def cmd_optimize():
    """Run full database optimization."""
    print("\n" + "=" * 60)
    print("DATABASE OPTIMIZATION")
    print("=" * 60)
    
    results = db_maintenance.full_maintenance()
    
    all_success = all(results.values())
    if all_success:
        print("\n✅ All optimization steps completed successfully")
    else:
        print("\n⚠️  Some optimization steps failed")
    
    print("=" * 60 + "\n")


def cmd_session_cleanup(args):
    """Clean up specific session data."""
    print("\n" + "=" * 60)
    print(f"SESSION {args.smoke_id} CLEANUP")
    print("=" * 60)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No data will be deleted")
    
    readings_deleted, tc_deleted = cleanup_manager.cleanup_session_data(
        smoke_id=args.smoke_id,
        keep_last_n=args.keep_last,
        dry_run=args.dry_run
    )
    
    print(f"\nResults:")
    print(f"  Readings deleted:    {readings_deleted:,}")
    print(f"  TC Readings deleted: {tc_deleted:,}")
    
    if not args.dry_run and readings_deleted > 0:
        print("\nRunning VACUUM to reclaim space...")
        db_maintenance.vacuum()
    
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Database management tool for autoSmoke',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show database statistics
  python manage_database.py stats
  
  # Clean up old data (dry run first!)
  python manage_database.py cleanup --dry-run
  python manage_database.py cleanup --reading-days 14
  
  # Optimize database
  python manage_database.py optimize
  
  # Vacuum database
  python manage_database.py vacuum
  
  # Clean up specific session
  python manage_database.py session-cleanup --smoke-id 5 --keep-last 1000
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Stats command
    subparsers.add_parser('stats', help='Show database statistics')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old data')
    cleanup_parser.add_argument(
        '--reading-days',
        type=int,
        default=30,
        help='Days to keep readings (default: 30)'
    )
    cleanup_parser.add_argument(
        '--event-days',
        type=int,
        default=90,
        help='Days to keep events (default: 90)'
    )
    cleanup_parser.add_argument(
        '--alert-days',
        type=int,
        default=60,
        help='Days to keep cleared alerts (default: 60)'
    )
    cleanup_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    # Vacuum command
    subparsers.add_parser('vacuum', help='Run VACUUM to reclaim space')
    
    # Analyze command
    subparsers.add_parser('analyze', help='Run ANALYZE to update statistics')
    
    # Optimize command
    subparsers.add_parser('optimize', help='Run full database optimization')
    
    # Session cleanup command
    session_parser = subparsers.add_parser('session-cleanup', help='Clean up specific session data')
    session_parser.add_argument(
        '--smoke-id',
        type=int,
        required=True,
        help='Smoke session ID to clean up'
    )
    session_parser.add_argument(
        '--keep-last',
        type=int,
        default=5000,
        help='Number of most recent readings to keep (default: 5000)'
    )
    session_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        if args.command == 'stats':
            cmd_stats()
        elif args.command == 'cleanup':
            cmd_cleanup(args)
        elif args.command == 'vacuum':
            cmd_vacuum()
        elif args.command == 'analyze':
            cmd_analyze()
        elif args.command == 'optimize':
            cmd_optimize()
        elif args.command == 'session-cleanup':
            cmd_session_cleanup(args)
        
        return 0
        
    except Exception as e:
        logger.error(f"Command failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

