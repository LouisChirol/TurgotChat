#!/usr/bin/env python3
"""
Script to clear Redis history for development and debugging purposes.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the Python path so we can import from app
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.redis import RedisService
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


def clear_all_sessions():
    """Clear all session histories from Redis."""
    try:
        redis_service = RedisService()
        
        # Get all keys that match our session pattern
        keys = redis_service.redis_client.keys("chat_history:*")
        
        if not keys:
            logger.info("No session histories found to clear")
            return
        
        # Delete all session histories
        deleted_count = redis_service.redis_client.delete(*keys)
        logger.info(f"Cleared {deleted_count} session histories from Redis")
        
    except Exception as e:
        logger.error(f"Error clearing Redis histories: {str(e)}")
        raise


def clear_session(session_id: str):
    """Clear a specific session history from Redis."""
    try:
        redis_service = RedisService()
        redis_service.clear_session_history(session_id)
        logger.info(f"Cleared session history for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {str(e)}")
        raise


def main():
    """Main function to handle command line arguments."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clear Redis chat histories")
    parser.add_argument(
        "--session", 
        type=str, 
        help="Clear specific session ID (if not provided, clears all sessions)"
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Clear all session histories"
    )
    
    args = parser.parse_args()
    
    try:
        if args.session:
            clear_session(args.session)
        elif args.all or not args.session:
            # Default behavior: clear all sessions
            clear_all_sessions()
            
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 