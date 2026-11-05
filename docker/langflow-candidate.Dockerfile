FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 langflow
COPY compliance/langflow-candidate-constraints.txt /app/langflow-candidate-constraints.txt
RUN pip install --no-cache-dir --timeout 120 --retries 3 pip==26.2.2 \
    && pip install --no-cache-dir --timeout 120 --retries 3 \
        --constraint /app/langflow-candidate-constraints.txt \
        langflow-base==1.13.1 pypdf==6.21.4 python-docx==1.2.0 \
        reportlab==4.5.1 psycopg==3.3.5 \
    && pip check
COPY review_core /app/review_core
COPY custom_components /app/custom_components
COPY flows /app/flows
COPY fixtures /app/fixtures
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY docs/DEPENDENCY_LICENSES.md /app/docs/DEPENDENCY_LICENSES.md
COPY licenses /app/licenses
RUN mkdir -p /app/artifacts \
    && chown -R 1000:1000 /app/review_core /app/custom_components /app/flows /app/artifacts
ENV PYTHONPATH=/app LANGFLOW_COMPONENTS_PATH=/app/custom_components
USER 1000
EXPOSE 7860
ENTRYPOINT ["python", "-m", "langflow", "run", "--host", "0.0.0.0", "--port", "7860"]
