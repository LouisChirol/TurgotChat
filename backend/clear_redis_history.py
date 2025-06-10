#!/usr/bin/env python3
"""
Utility script to clear Redis chat history.
Usage: python clear_redis_history.py [session_id]
"""

import sys

from redis_service import RedisService


def clear_session_history(session_id: str):
    """Clear history for a specific session."""
    redis_service = RedisService()
    redis_service.clear_history(session_id)
    print(f"✅ Cleared history for session: {session_id}")

def clear_all_history():
    """Clear all chat history from Redis."""
    redis_service = RedisService()
    
    # Get all keys matching the chat pattern
    keys = redis_service.redis_client.keys("chat:*")
    
    if not keys:
        print("ℹ️  No chat history found in Redis")
        return
    
    # Delete all chat keys
    if keys:
        redis_service.redis_client.delete(*keys)
        print(f"✅ Cleared {len(keys)} chat sessions from Redis")
    
    # Clear in-memory histories
    redis_service.memories.clear()
    print("✅ Cleared all in-memory chat histories")

def main():
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        clear_session_history(session_id)
    else:
        print("Choose an option:")
        print("1. Clear all chat history")
        print("2. Clear specific session history")
        
        choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            confirm = input("Are you sure you want to clear ALL chat history? (y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                clear_all_history()
            else:
                print("❌ Operation cancelled")
        elif choice == "2":
            session_id = input("Enter session ID to clear: ").strip()
            if session_id:
                clear_session_history(session_id)
            else:
                print("❌ Session ID cannot be empty")
        else:
            print("❌ Invalid choice")

if __name__ == "__main__":
    main() if __name__ == "__main__":
    main() 