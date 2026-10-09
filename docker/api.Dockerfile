FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.lock ./
RUN pip install --no-cache-dir --no-deps --timeout 120 --retries 10 -r requirements.lock
COPY pyproject.toml README.md LICENSE ./
COPY review_core ./review_core
COPY custom_components ./custom_components
COPY api ./api
COPY scripts ./scripts
COPY flows ./flows
RUN pip install --no-cache-dir --no-deps . && mkdir -p /app/documents /app/config && chown -R appuser:appuser /app/documents /app/config
USER appuser
EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
