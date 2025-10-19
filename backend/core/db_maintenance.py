"""Database maintenance utilities for SQLite.

Handles vacuum, analyze, and other maintenance operations.
"""

import logging
import os
from pathlib import Path
from sqlmodel import create_engine, text
from db.session import get_session_sync

logger = logging.getLogger(__name__)


class DatabaseMaintenance:
    """Database maintenance operations."""
    
    @staticmethod
    def vacuum() -> bool:
        """
        Run VACUUM on the database to reclaim space and defragment.
        
        VACUUM rebuilds the database file, repacking it into a minimal amount
        of disk space. This is especially important after deleting large amounts
        of data.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info("Running VACUUM on database...")
        logger.info("This may take a few moments for large databases")
        logger.info("=" * 60)
        
        try:
            with get_session_sync() as session:
                # Get database size before
                db_path = Path("smoker.db")
                if db_path.exists():
                    size_before = db_path.stat().st_size / (1024 * 1024)  # MB
                    logger.info(f"Database size before: {size_before:.2f} MB")
                
                # Run VACUUM
                connection = session.connection()
                connection.execute(text("VACUUM"))
                session.commit()
                
                # Get database size after
                if db_path.exists():
                    size_after = db_path.stat().st_size / (1024 * 1024)  # MB
                    saved = size_before - size_after
                    logger.info(f"Database size after: {size_after:.2f} MB")
                    logger.info(f"Space reclaimed: {saved:.2f} MB ({(saved/size_before*100):.1f}%)")
                
                logger.info("✅ VACUUM completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"❌ VACUUM failed: {e}")
            return False
    
    @staticmethod
    def analyze() -> bool:
        """
        Run ANALYZE to update query planner statistics.
        
        ANALYZE gathers statistics about the contents of tables and indexes,
        which helps SQLite's query planner choose better execution plans.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Running ANALYZE on database...")
        
        try:
            with get_session_sync() as session:
                connection = session.connection()
                connection.execute(text("ANALYZE"))
                session.commit()
                logger.info("✅ ANALYZE completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"❌ ANALYZE failed: {e}")
            return False
    
    @staticmethod
    def optimize() -> bool:
        """
        Run optimization pragma commands for better performance.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Running database optimization...")
        
        try:
            with get_session_sync() as session:
                connection = session.connection()
                
                # Optimize database
                connection.execute(text("PRAGMA optimize"))
                
                # Set pragmas for better performance
                connection.execute(text("PRAGMA journal_mode=WAL"))  # Write-Ahead Logging
                connection.execute(text("PRAGMA synchronous=NORMAL"))  # Balance between safety and speed
                connection.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
                connection.execute(text("PRAGMA temp_store=MEMORY"))  # Use memory for temp tables
                
                session.commit()
                logger.info("✅ Database optimization completed")
                return True
                
        except Exception as e:
            logger.error(f"❌ Database optimization failed: {e}")
            return False
    
    @staticmethod
    def full_maintenance() -> dict:
        """
        Run full maintenance: ANALYZE, VACUUM, and optimization.
        
        Returns:
            Dictionary with results of each operation
        """
        logger.info("=" * 60)
        logger.info("Starting FULL database maintenance")
        logger.info("=" * 60)
        
        results = {
            'analyze': False,
            'vacuum': False,
            'optimize': False,
        }
        
        # Run ANALYZE first (helps with query planning)
        results['analyze'] = DatabaseMaintenance.analyze()
        
        # Run VACUUM (reclaim space)
        results['vacuum'] = DatabaseMaintenance.vacuum()
        
        # Run optimization
        results['optimize'] = DatabaseMaintenance.optimize()
        
        logger.info("=" * 60)
        logger.info("Full maintenance complete!")
        logger.info(f"  ANALYZE: {'✅' if results['analyze'] else '❌'}")
        logger.info(f"  VACUUM: {'✅' if results['vacuum'] else '❌'}")
        logger.info(f"  OPTIMIZE: {'✅' if results['optimize'] else '❌'}")
        logger.info("=" * 60)
        
        return results
    
    @staticmethod
    def get_database_info() -> dict:
        """Get database information and statistics."""
        try:
            with get_session_sync() as session:
                connection = session.connection()
                
                # Get page count and size
                page_count = connection.execute(text("PRAGMA page_count")).fetchone()[0]
                page_size = connection.execute(text("PRAGMA page_size")).fetchone()[0]
                freelist_count = connection.execute(text("PRAGMA freelist_count")).fetchone()[0]
                
                total_size_mb = (page_count * page_size) / (1024 * 1024)
                free_size_mb = (freelist_count * page_size) / (1024 * 1024)
                used_size_mb = total_size_mb - free_size_mb
                
                # Get journal mode
                journal_mode = connection.execute(text("PRAGMA journal_mode")).fetchone()[0]
                
                # Get table info
                tables = connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                ).fetchall()
                
                table_stats = {}
                for (table_name,) in tables:
                    if not table_name.startswith('sqlite_'):
                        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
                        count = connection.execute(count_query).fetchone()[0]
                        table_stats[table_name] = count
                
                return {
                    'total_size_mb': round(total_size_mb, 2),
                    'used_size_mb': round(used_size_mb, 2),
                    'free_size_mb': round(free_size_mb, 2),
                    'fragmentation_pct': round((free_size_mb / total_size_mb * 100), 1) if total_size_mb > 0 else 0,
                    'page_count': page_count,
                    'page_size': page_size,
                    'journal_mode': journal_mode,
                    'table_counts': table_stats
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {}


# Global maintenance instance
db_maintenance = DatabaseMaintenance()

