# Build stage: Python 3.12.8-bookworm
FROM docker.io/library/python@sha256:ab70aee8e1bc6ffe4f95953ee2a98ca545123195a2b56d4338c7ea8ff5744a20 as build-python

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y libsndfile1 libspeexdsp-dev git && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the application into the container.
COPY pyproject.toml README.md uv.lock /app
COPY assets /app/assets
COPY app /app/app

RUN --mount=type=cache,target=/root/.cache \
    cd /app && \
    uv sync \
        --frozen \
        --no-group dev \
        --group prod

# runtime stage: Python 3.12.8-slim-bookworm
FROM docker.io/library/python@sha256:ab70aee8e1bc6ffe4f95953ee2a98ca545123195a2b56d4338c7ea8ff5744a20

ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN addgroup --system --gid 1001 appuser && adduser --system --uid 1001 --no-create-home --ingroup appuser appuser

WORKDIR /app
COPY --from=build-python --chown=appuser:appuser /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y libsndfile1 libspeexdsp-dev && \
    rm -rf /var/lib/apt/lists/*

# Download models as the root user
RUN /app/.venv/bin/python -c "import openwakeword.utils; openwakeword.utils.download_models(model_names=['none'])"

# Set the user to 'appuser'
USER appuser

# Expose the application port
EXPOSE 8080

# Start the application as the non-root user
CMD ["fastapi", "run", "app/main.py", "--proxy-headers", "--host", "0.0.0.0", "--port", "8080"]
