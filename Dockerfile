FROM python:3.11-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications first for Docker layer caching
COPY pyproject.toml requirements.txt README.md ./

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY src ./src
COPY frontend ./frontend
COPY examples ./examples

# Install local package
RUN pip install --no-cache-dir -e .

# Security best practice: create and run as non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Render injects the PORT environment variable dynamically
ENV PORT=10000
ENV PYTHONPATH=/app/src
ENV WHISPER_MODEL=base
ENV WHISPER_COMPUTE_TYPE=int8
ENV WHISPER_DEVICE=cpu

EXPOSE ${PORT}

CMD uvicorn mediscribe.main:app --host 0.0.0.0 --port ${PORT}
