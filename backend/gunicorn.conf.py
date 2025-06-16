import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "gunicorn-access.log")
errorlog = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "gunicorn-error.log")
loglevel = "info"

# Process naming
proc_name = "colbert-backend"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
keyfile = None
certfile = None 