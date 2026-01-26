# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependencies first for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv
RUN uv sync --frozen --no-cache

# Copy application files
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create necessary directories and ensure they are writable
# We use /tmp/riparr for transient files and /app/config for persistent ones
RUN mkdir -p /app/config /tmp/riparr/downloads /media/Music && \
    chmod -R 777 /app/config /tmp/riparr /media/Music

# Expose port 5000
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=backend/app.py
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:////app/config/riparr.db
ENV PYTHONPATH=/app
ENV DOCKER_CONTAINER=true

# Redirect cache and home to writable volume
ENV HOME=/app/config
ENV XDG_CACHE_HOME=/app/config

# Run the application with uv
CMD ["uv", "run", "python", "-m", "backend.app"]
