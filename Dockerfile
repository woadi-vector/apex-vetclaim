# APEX VetClaim — Cloud Run deployment image
# Slack bot + ADK agent + Arize Phoenix MCP (subprocess via npx).
# Mirrors the APEX Approve Dockerfile pattern.

FROM python:3.12-slim

# Install Node.js 20 (required for the @arizeai/phoenix-mcp subprocess)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Pre-install Phoenix MCP globally so cold starts don't pay the npm-fetch cost
RUN npm install -g @arizeai/phoenix-mcp@latest && \
    npm cache clean --force

# Install uv for Python dependency management
RUN pip install --no-cache-dir uv==0.11.23

WORKDIR /app

# Install Python deps first (better Docker layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source
COPY src/ ./src/
COPY README.md LICENSE ./

# Install the project itself
RUN uv sync --frozen --no-dev

# Cloud Run config
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_CLOUD_PROJECT=apex-vetclaim
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV GEMINI_MODEL=gemini-2.5-flash
ENV PHOENIX_PROJECT_NAME=apex-vetclaim

# Sanity check that phoenix-mcp is on PATH
RUN which phoenix-mcp && phoenix-mcp --help 2>&1 | head -3 || true

CMD ["uv", "run", "uvicorn", "apex_vetclaim.server:app", "--host", "0.0.0.0", "--port", "8080"]
