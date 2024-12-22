FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.5.9 /uv /uvx /bin/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -s /sbin/nologin -M appuser

# Install system dependencies
RUN apt-get update && apt-get install -y libsndfile1 libspeexdsp-dev git && \
    rm -rf /var/lib/apt/lists/*

# Copy the application into the container.
COPY pyproject.toml README.md uv.lock /app
COPY app /app/app
COPY assets /app/assets
RUN uv sync --frozen --no-cache

# Download models as the root user
RUN /app/.venv/bin/python -c "import openwakeword.utils; openwakeword.utils.download_models(model_names=['none'])"

RUN chmod 775 -R /app

# # Switch to non-root user
USER appuser

# Expose the application port
EXPOSE 8080

# Set up the health check
HEALTHCHECK --interval=20s --timeout=20s --start-period=5s --retries=3 CMD ["curl", "--fail", "-so", "/dev/null", "http://127.0.0.1:8080/health"]

# Start the application as the non-root user
CMD ["/app/.venv/bin/fastapi", "run", "app/main.py", "--proxy-headers", "--host", "0.0.0.0", "--port", "8080"]
