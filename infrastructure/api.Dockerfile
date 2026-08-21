# AegisOps API Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install api-specific runtime deps if needed (uvicorn/fastapi are in requirements.txt)
COPY api/ api/
COPY database/ database/
COPY agents/ agents/
COPY armoriq/ armoriq/
COPY mcp_servers/ mcp_servers/

# Run as non-root user
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
