FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y libsndfile1 libspeexdsp-dev git && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -g 1000 appuser && useradd -m -u 1000 -g appuser -s /bin/bash appuser

# Copy and install the wheel file
ARG WHEEL_FILE=my_wheel.whl
COPY dist/${WHEEL_FILE} /tmp/${WHEEL_FILE}
RUN pip install /tmp/${WHEEL_FILE} && rm /tmp/${WHEEL_FILE} && \
    pip install --force openwakeword@git+https://github.com/stkr22/openWakeWord.git@af84a81

# Set up the application directory and permissions
RUN mkdir -p /app && chown -R appuser:appuser /app
COPY assets/ /app/assets/
RUN chown -R appuser:appuser /app/assets

# Download models as the root user
RUN python -c "import openwakeword.utils; openwakeword.utils.download_models(model_names=['none'])"

# Switch to non-root user
USER appuser

# Set the working directory for the non-root user
WORKDIR /app

# Expose the application port
EXPOSE 8080

# Set up the health check
HEALTHCHECK --interval=20s --timeout=20s --start-period=5s --retries=3 CMD ["curl", "--fail", "-so", "/dev/null", "http://127.0.0.1:8080/health"]

# Start the application as the non-root user
ENTRYPOINT ["uvicorn", "private_assistant_comms_bridge.main:app", "--host", "0.0.0.0", "--port", "8080"]
