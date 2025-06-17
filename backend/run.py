#!/usr/bin/env python3
"""
Development runner for Turgot API.

This script provides a convenient way to run the application during development.
"""

import uvicorn
from app.api.main import app

if __name__ == "__main__":
    # Run with reload for development
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True,
        log_level="info"
    ) 