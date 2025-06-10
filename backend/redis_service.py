import json
import os
from datetime import timedelta
from typing import Dict
from urllib.parse import urlparse

import redis
from dotenv import load_dotenv
from langchain_core.chat_history import InMemoryChatMessageHistory
from loguru import logger

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
logger.info(f"Connecting to Redis at: {REDIS_URL}")

# Parse Redis URL
redis_url = urlparse(REDIS_URL)
redis_host = redis_url.hostname
redis_port = redis_url.port or 6379

class RedisService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            decode_responses=True,
        )
        self.session_ttl = timedelta(
            hours=1
        )  # 1 hour TTL for sessions (RGPD compliance)
        self.memories = {}  # Store InMemoryChatMessageHistory instances

    def get_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """Get a ConversationBufferMemory instance for a session"""
        if session_id not in self.memories:
            self.memories[session_id] = InMemoryChatMessageHistory()
            # Load existing messages from Redis if any
            messages = self.redis_client.lrange(f"chat:{session_id}", 0, -1)
            for message_json in messages:
                message = json.loads(message_json)
                if message["role"] == "user":
                    self.memories[session_id].add_user_message(message["content"])
                else:
                    self.memories[session_id].add_ai_message(message["content"])
        return self.memories[session_id]

    def store_message(self, session_id: str, message: Dict) -> None:
        """Store a message in the history for a session"""
        history = self.get_history(session_id)

        if message["role"] == "user":
            history.add_user_message(message["content"])
        else:
            history.add_ai_message(message["content"])

        # Store message in Redis
        message_json = json.dumps(message)
        self.redis_client.rpush(f"chat:{session_id}", message_json)
        self.redis_client.expire(
            f"chat:{session_id}", int(self.session_ttl.total_seconds())
        )

        return history

    def clear_history(self, session_id: str) -> None:
        """Clear history for a session"""
        if session_id in self.memories:
            self.memories[session_id].clear()
        # Clear from Redis as well
        self.redis_client.delete(f"chat:{session_id}")


# Create a singleton instance
redis_service = RedisService()
