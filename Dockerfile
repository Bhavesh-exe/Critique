# Universal Multi-Stage Dockerfile for Reflex App (Critique)
# Supports Hugging Face Spaces, Render, Railway, Fly.io, and Cloud Run

FROM python:3.11-slim as base

# Install system dependencies & Node.js for Reflex / Next.js frontend bundling
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Initialize and build frontend
RUN reflex init
RUN reflex export --frontend-only --no-zip

# Expose backend (8000) and frontend (3000)
EXPOSE 3000 8000

ENV PYTHONUNBUFFERED=1

# Run Reflex in production mode
CMD ["reflex", "run", "--env", "prod"]
