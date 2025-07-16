#!/usr/bin/env python3
"""
Management script for incremental document processing.
Provides utilities to check status, force reprocessing, and manage the tracking database.
"""

import argparse
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from loguru import logger


class IncrementalManager:
    def __init__(self, db_path: str = "chroma_db/chroma.sqlite3"):
        self.db_path = db_path
    
    def get_tracking_stats(self) -> Dict[str, any]:
        """Get statistics about tracked documents."""
        with sqlite3.connect(self.db_path) as conn:
            # Total tracked files
            cursor = conn.execute("SELECT COUNT(*) FROM document_tracking")
            total_files = cursor.fetchone()[0]
            
            # Files by data source
            cursor = conn.execute("""
                SELECT data_source, COUNT(*) as count 
                FROM document_tracking 
                GROUP BY data_source
            """)
            by_source = dict(cursor.fetchall())
            
            # Total chunks
            cursor = conn.execute("SELECT SUM(chunk_count) FROM document_tracking")
            total_chunks = cursor.fetchone()[0] or 0
            
            # Last processing time
            cursor = conn.execute("SELECT MAX(processed_at) FROM document_tracking")
            last_processed = cursor.fetchone()[0]
            
            return {
                'total_files': total_files,
                'by_source': by_source,
                'total_chunks': total_chunks,
                'last_processed': last_processed
            }
    
    def list_tracked_files(self, data_source: str = None) -> List[Tuple[str, str, float, int]]:
        """List all tracked files with their metadata."""
        query = """
            SELECT file_path, data_source, processed_at, chunk_count 
            FROM document_tracking
        """
        params = []
        
        if data_source:
            query += " WHERE data_source = ?"
            params.append(data_source)
        
        query += " ORDER BY processed_at DESC"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def check_file_status(self, file_path: str) -> Dict[str, any]:
        """Check the status of a specific file."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT last_modified, content_hash, data_source, processed_at, chunk_count 
                FROM document_tracking 
                WHERE file_path = ?
            """, (file_path,))
            row = cursor.fetchone()
            
            if not row:
                return {'status': 'not_tracked'}
            
            return {
                'status': 'tracked',
                'last_modified': row[0],
                'content_hash': row[1],
                'data_source': row[2],
                'processed_at': row[3],
                'chunk_count': row[4]
            }
    
    def remove_file_tracking(self, file_path: str):
        """Remove tracking for a specific file."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM document_tracking WHERE file_path = ?", (file_path,))
            conn.commit()
        logger.info(f"Removed tracking for: {file_path}")
    
    def clear_all_tracking(self):
        """Clear all tracking data (forces full reprocessing on next run)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM document_tracking")
            conn.commit()
        logger.info("Cleared all tracking data. Next run will process all files.")
    
    def cleanup_deleted_files(self):
        """Remove tracking for files that no longer exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT file_path FROM document_tracking")
            tracked_files = [row[0] for row in cursor.fetchall()]
        
        deleted_count = 0
        for file_path in tracked_files:
            if not Path(file_path).exists():
                self.remove_file_tracking(file_path)
                deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} deleted files from tracking")
        else:
            logger.info("No deleted files found in tracking")


def format_timestamp(timestamp: float) -> str:
    """Format a timestamp for display."""
    if timestamp:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    return "Never"


def main():
    parser = argparse.ArgumentParser(description="Manage incremental document processing")
    parser.add_argument("command", choices=[
        "status", "list", "check", "remove", "clear", "cleanup"
    ], help="Command to execute")
    parser.add_argument("--file", help="File path for check/remove commands")
    parser.add_argument("--source", help="Data source filter for list command")
    parser.add_argument("--db-path", default="chroma_db/chroma.sqlite3", 
                       help="Path to the tracking database")
    
    args = parser.parse_args()
    
    manager = IncrementalManager(args.db_path)
    
    if args.command == "status":
        stats = manager.get_tracking_stats()
        print(f"\n📊 Tracking Statistics:")
        print(f"   Total files tracked: {stats['total_files']}")
        print(f"   Total chunks: {stats['total_chunks']}")
        print(f"   Last processed: {format_timestamp(stats['last_processed'])}")
        
        print(f"\n📁 By data source:")
        for source, count in stats['by_source'].items():
            print(f"   {source}: {count} files")
    
    elif args.command == "list":
        files = manager.list_tracked_files(args.source)
        if not files:
            print("No tracked files found.")
            return
        
        print(f"\n📋 Tracked Files:")
        for file_path, data_source, processed_at, chunk_count in files:
            print(f"   📄 {file_path}")
            print(f"      Source: {data_source}")
            print(f"      Chunks: {chunk_count}")
            print(f"      Processed: {format_timestamp(processed_at)}")
            print()
    
    elif args.command == "check":
        if not args.file:
            print("Error: --file argument required for check command")
            return
        
        status = manager.check_file_status(args.file)
        print(f"\n🔍 File Status: {args.file}")
        if status['status'] == 'not_tracked':
            print("   Status: Not tracked")
        else:
            print(f"   Status: Tracked")
            print(f"   Data source: {status['data_source']}")
            print(f"   Chunks: {status['chunk_count']}")
            print(f"   Last modified: {format_timestamp(status['last_modified'])}")
            print(f"   Processed: {format_timestamp(status['processed_at'])}")
            print(f"   Content hash: {status['content_hash'][:16]}...")
    
    elif args.command == "remove":
        if not args.file:
            print("Error: --file argument required for remove command")
            return
        
        manager.remove_file_tracking(args.file)
    
    elif args.command == "clear":
        confirm = input("Are you sure you want to clear all tracking data? (y/N): ")
        if confirm.lower() == 'y':
            manager.clear_all_tracking()
        else:
            print("Operation cancelled.")
    
    elif args.command == "cleanup":
        manager.cleanup_deleted_files()


if __name__ == "__main__":
    main() 