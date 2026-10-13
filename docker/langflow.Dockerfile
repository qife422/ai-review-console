FROM langflowai/langflow:1.11.6@sha256:5338f6851fbab3d0476f7701dacbe749f58fa81a4c1317ad1d52164ce1231a14

USER root
WORKDIR /app
RUN pip install --no-cache-dir --timeout 120 --retries 10 pypdf==6.16.2 python-docx==1.2.0 reportlab==4.5.1
COPY review_core /app/review_core
COPY custom_components /app/custom_components
COPY flows /app/flows
COPY fixtures /app/fixtures
RUN mkdir -p /app/artifacts && chown -R 1000:1000 /app/review_core /app/custom_components /app/flows /app/artifacts
ENV PYTHONPATH=/app LANGFLOW_COMPONENTS_PATH=/app/custom_components
USER 1000
