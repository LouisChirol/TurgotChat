# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo 'export PATH="/root/.cargo/bin:$PATH"' >> /root/.bashrc && \
    . /root/.bashrc

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN . /root/.bashrc && \
    uv venv && \
    . .venv/bin/activate && \
    uv pip install -e .

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/database/chroma_db && \
    chmod 777 /app/logs /app/database/chroma_db

# Copy the rest of the application
COPY . .

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 