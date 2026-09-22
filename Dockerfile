# ==============================================================================
# BEACON Backend Production Dockerfile
# Multi-stage build for optimized production image
# ==============================================================================

# ==============================================================================
# Stage 1: Python Dependencies Builder
# ==============================================================================
FROM python:3.10-slim AS python-builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==============================================================================
# Stage 2: Node.js for Lighthouse (optional, only if needed)
# ==============================================================================
FROM node:18-alpine AS node-lighthouse

# Install Lighthouse and axe-core globally
RUN npm install -g lighthouse@latest axe-core@latest

# ==============================================================================
# Stage 3: Final Production Image
# ==============================================================================
FROM python:3.10-slim

# Set environment to production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENVIRONMENT=production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq5 \
    gnupg \
    # Node.js for Lighthouse
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    # Chromium dependencies for Camoufox/Playwright
    && apt-get install -y --no-install-recommends \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash beacon && \
    mkdir -p /app /app/logs /app/chroma_db /app/data && \
    chown -R beacon:beacon /app

WORKDIR /app

# Copy Python packages from builder
COPY --from=python-builder /root/.local /home/beacon/.local

# Copy Lighthouse from Node stage
COPY --from=node-lighthouse /usr/local/lib/node_modules/lighthouse /usr/local/lib/node_modules/lighthouse
RUN ln -s /usr/local/lib/node_modules/lighthouse/cli/index.js /usr/local/bin/lighthouse && \
    chmod +x /usr/local/bin/lighthouse

# Copy application code and offline axe-core bundle
COPY --chown=beacon:beacon app/ ./app/
COPY --chown=beacon:beacon rag/ ./rag/
COPY --chown=beacon:beacon corpus/ ./corpus/
COPY --chown=beacon:beacon axe-core/axe.min.js ./axe-core/axe.min.js

# Switch to non-root user
USER beacon

# Add local Python packages to PATH
ENV PATH=/home/beacon/.local/bin:$PATH

# Install browser runtime for Camoufox (as non-root user)
RUN python -m camoufox fetch || echo "Camoufox fetch failed, will fallback to Playwright"

# Health check (supports dynamic PORT or default 8000)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Expose port
EXPOSE 8000

# Start application with dynamic Render port support
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
