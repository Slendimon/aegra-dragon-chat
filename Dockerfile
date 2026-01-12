FROM python:3.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

# Create non-root user for runtime
RUN addgroup --system app && adduser --system --ingroup app app

# ======================================================
# Builder (installs dependencies)
# ======================================================
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy metadata & source
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

# Install project (build wheel and dependencies)
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir .

# ======================================================
# Final runtime
# ======================================================
FROM base AS final

# Install minimal runtime libs (psycopg[binary] handles PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python deps from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy runtime assets required by Aegra
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/
COPY aegra.json ./aegra.json
COPY auth.py ./auth.py
COPY graphs/ ./graphs/
COPY src/ ./src/

# Expose default port
EXPOSE 8000

# Environment defaults
ENV PORT=8000
ENV AUTH_TYPE=noop
ENV DEBUG=true

# Use non-root user
USER app

# ======================================================
# Default CMD
# ======================================================
# Alembic migrations + Uvicorn app startup
CMD sh -c "\
    echo 'Running database migrations...' && \
    alembic upgrade head && \
    echo 'Starting Aegra server on port ${PORT}...' && \
    uvicorn src.agent_server.main:app --host 0.0.0.0 --port ${PORT} \
"
