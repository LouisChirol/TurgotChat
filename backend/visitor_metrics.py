import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Set

from prometheus_client import Counter, Gauge, Histogram

# Metrics for visitor tracking
active_visitors = Gauge('active_visitors', 'Number of currently active visitors')
total_visitors = Counter('total_visitors', 'Total number of unique visitors')
visitor_sessions = Counter('visitor_sessions', 'Total number of visitor sessions')
messages_sent = Counter('messages_sent', 'Total number of messages sent')
average_session_duration = Histogram('session_duration_seconds', 'Duration of visitor sessions')

# In-memory storage for active sessions
active_sessions: Dict[str, datetime] = {}
session_lock = threading.Lock()

def track_session_start(session_id: str) -> None:
    """Track the start of a new session."""
    with session_lock:
        if session_id not in active_sessions:
            active_sessions[session_id] = datetime.now()
            visitor_sessions.inc()
            active_visitors.inc()
            total_visitors.inc()

def track_session_end(session_id: str) -> None:
    """Track the end of a session and record its duration."""
    with session_lock:
        if session_id in active_sessions:
            start_time = active_sessions[session_id]
            duration = (datetime.now() - start_time).total_seconds()
            average_session_duration.observe(duration)
            del active_sessions[session_id]
            active_visitors.dec()

def track_message(session_id: str) -> None:
    """Track a message being sent."""
    messages_sent.inc()
    # Ensure the session is tracked
    track_session_start(session_id)

def cleanup_expired_sessions(timeout_minutes: int = 30) -> None:
    """Clean up sessions that have been inactive for too long."""
    while True:
        with session_lock:
            now = datetime.now()
            expired = [
                session_id for session_id, start_time in active_sessions.items()
                if now - start_time > timedelta(minutes=timeout_minutes)
            ]
            for session_id in expired:
                track_session_end(session_id)
        time.sleep(60)  # Check every minute

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
cleanup_thread.start() 