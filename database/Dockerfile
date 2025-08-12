FROM python:3.13-slim

# Build context is ./database
WORKDIR /app/database

# System deps if needed
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Copy package metadata and install deps with uv (editable install)
COPY pyproject.toml ./pyproject.toml
RUN pip install uv && uv pip install --system --no-cache -e .

# Copy the database code
COPY . ./

ENV PYTHONUNBUFFERED=1

# Default command can be overridden by `docker compose run ... -- <args>`
CMD ["python", "run_update.py", "--cleanup-old-dumps"]