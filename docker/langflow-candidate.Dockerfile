FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y apt=2.6.2 libapt-pkg6.0=2.6.2 libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 langflow
COPY compliance/langflow-candidate-build-tools.lock compliance/langflow-candidate.lock /app/
RUN python -m pip install --no-cache-dir --timeout 120 --retries 3 --require-hashes --only-binary=:all: \
        -r /app/langflow-candidate-build-tools.lock \
    && python -m pip install --no-cache-dir --timeout 120 --retries 3 --require-hashes --no-build-isolation \
        -r /app/langflow-candidate.lock \
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
