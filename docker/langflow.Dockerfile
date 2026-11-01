FROM langflowai/langflow:1.11.6@sha256:5338f6851fbab3d0476f7701dacbe749f58fa81a4c1317ad1d52164ce1231a14

USER root
WORKDIR /app
RUN pip install --no-cache-dir --timeout 120 --retries 10 \
    certifi==2026.10.23 pypdf==6.21.4 python-docx==1.2.0 reportlab==4.5.1 \
    aiohttp==3.14.4 authlib==1.9.1 black==26.10.1 brotli==1.2.1 \
    dnspython==2.9.0 fastmcp==3.4.10 fastmcp-slim==3.4.10 fsspec==2026.6.0 \
    gitpython==3.2.1 joserfc==1.7.6 langchain-nvidia-ai-endpoints==1.5.0 \
    langgraph==1.2.14 langgraph-sdk==0.4.6 litellm==1.103.1 mako==1.4.2 \
    mcp==1.30.0 mem0ai==2.0.18 multidict==6.9.1 nltk==3.10.4 \
    pyasn1==0.6.5 pyjwt==2.15.0 pymongo==4.18.3 transformers==5.10.0 \
    urllib3==2.8.0 yarl==1.25.1
COPY review_core /app/review_core
COPY custom_components /app/custom_components
COPY flows /app/flows
COPY fixtures /app/fixtures
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY docs/DEPENDENCY_LICENSES.md /app/docs/DEPENDENCY_LICENSES.md
RUN mkdir -p /app/artifacts && chown -R 1000:1000 /app/review_core /app/custom_components /app/flows /app/artifacts
ENV PYTHONPATH=/app LANGFLOW_COMPONENTS_PATH=/app/custom_components
USER 1000
