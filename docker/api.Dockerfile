FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.lock ./
RUN pip install --no-cache-dir --timeout 120 --retries 10 pip==26.2.2 \
    && pip install --no-cache-dir --no-deps --timeout 120 --retries 10 -r requirements.lock
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY docs/DEPENDENCY_LICENSES.md ./docs/DEPENDENCY_LICENSES.md
COPY review_core ./review_core
COPY custom_components ./custom_components
COPY api ./api
COPY scripts ./scripts
COPY flows ./flows
RUN pip install --no-cache-dir --no-deps . && mkdir -p /app/documents /app/config && chown -R appuser:appuser /app/documents /app/config
USER appuser
EXPOSE 8000
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
