FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    jq curl libpq-dev gcc postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --upgrade pip
RUN pip install "prometheus_client<0.20"
RUN pip install "matrix-synapse[all]"
RUN pip install --upgrade "pyOpenSSL>=24.2.1" "cryptography>=43,<48"

# código do synapse (com suas modificações locais)
COPY synapse       /app/synapse
COPY rust          /app/rust
COPY modules       /app/modules
COPY pyproject.toml Cargo.toml Cargo.lock build_rust.py README.rst /app/

RUN pip install -e /app

ENV PYTHONPATH=/app

EXPOSE 3000
CMD ["python", "-m", "synapse.app.homeserver", "--config-path", "/data/homeserver.yaml"]
