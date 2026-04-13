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
RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --prefer-binary -r /tmp/scireplicbench-requirements.txt

COPY pyproject.toml README.md /opt/scireplicbench/
COPY src /opt/scireplicbench/src
RUN python -m pip install -e /opt/scireplicbench

RUN mkdir -p /workspace/input /workspace/output /workspace/submission /workspace/logs

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["tail", "-f", "/dev/null"]
