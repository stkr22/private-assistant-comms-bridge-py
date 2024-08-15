FROM python:3.11

ENV PYTHONUNBUFFERED=1


# Install system dependencies
RUN apt-get update && apt-get install -y libsndfile1 libspeexdsp-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy and install the wheel file
ARG WHEEL_FILE=my_wheel.whl
COPY dist/${WHEEL_FILE} /tmp/${WHEEL_FILE}
RUN pip install /tmp/${WHEEL_FILE} && rm /tmp/${WHEEL_FILE}

# Set up the application directory
RUN mkdir /app
COPY assets/ /app/
WORKDIR /app

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=20s --start-period=5s --retries=3 CMD ["curl", "--fail", "-so", "/dev/null", "http://127.0.0.1:80/health"]

ENTRYPOINT ["uvicorn", "private_assistant_comms_bridge.main:app", "--host", "0.0.0.0", "--port", "80"]
