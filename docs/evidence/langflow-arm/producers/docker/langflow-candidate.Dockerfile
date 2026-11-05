FROM python:3.12.16-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
ARG TARGETARCH

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y apt=2.6.2 libapt-pkg6.0=2.6.2 libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 langflow
COPY compliance/langflow-candidate-build-tools.lock compliance/langflow-candidate.lock /app/
COPY compliance/langflow-candidate-build-tools-arm64.lock compliance/langflow-candidate-arm64.lock /app/
RUN case "$TARGETARCH" in \
        amd64) arc_tools=/app/langflow-candidate-build-tools.lock; arc_lock=/app/langflow-candidate.lock; arc_machine=x86_64 ;; \
        arm64) arc_tools=/app/langflow-candidate-build-tools-arm64.lock; arc_lock=/app/langflow-candidate-arm64.lock; arc_machine=aarch64 ;; \
        *) echo 'Unsupported candidate target architecture' >&2; exit 1 ;; \
    esac \
    && ARC_EXPECTED_MACHINE="$arc_machine" python -c 'import os,platform; assert platform.machine() == os.environ["ARC_EXPECTED_MACHINE"], "Candidate interpreter architecture mismatch"' \
    && python -m pip install --no-cache-dir --timeout 120 --retries 3 --require-hashes --only-binary=:all: \
        -r "$arc_tools" \
    && python -m pip install --no-cache-dir --timeout 120 --retries 3 --require-hashes --no-build-isolation \
        -r "$arc_lock" \
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
