FROM python:3.11-slim-bookworm

ARG REQUIREMENTS_FILE=environments/requirements.txt

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY ${REQUIREMENTS_FILE} /tmp/scireplicbench-requirements.txt
# Install scientific deps with `uv`, whose resolver handles the deep
# backtracking that scanpy + squidpy + spatialdata provoke in pip 24.3+.
# SciReplicBench itself is not installed inside the container on purpose:
# the agent drives the sandbox through Inspect's shell/python channels
# and installing the project would pull inspect-ai's transitive closure
# (textual, etc.) for no user-visible benefit.
RUN python -m pip install --upgrade pip setuptools wheel uv && \
    uv pip install --system --no-cache --compile-bytecode \
        -r /tmp/scireplicbench-requirements.txt

RUN mkdir -p /workspace/input /workspace/output /workspace/submission /workspace/logs

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["tail", "-f", "/dev/null"]
