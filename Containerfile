FROM python:3.11-slim

ENV PYTHONUNBUFFERED 1

ARG WHEEL_FILE=my_wheel.wh

# Copy only the wheel file
COPY dist/${WHEEL_FILE} /tmp/${WHEEL_FILE}

# Install the package
RUN pip install /tmp/${WHEEL_FILE} && \
    rm /tmp/${WHEEL_FILE}

RUN apt-get install libsndfile1

# Create a non-root user and switch to it
RUN groupadd -r apiuser && useradd -r -m -g apiuser apiuser

# Switch to the non-root user
USER apiuser

EXPOSE 80

HEALTHCHECK --interval=20s --timeout=20s --start-period=5s --retries=3 CMD ["curl --fail -so /dev/null http://localhost:80/health"]

ENTRYPOINT [ "uvicorn", "private_assistant_comms_bridge.main:app", "--host",  "0.0.0.0", "--port", "80" ]
