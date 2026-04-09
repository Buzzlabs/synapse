FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    jq \
    curl \
    libpq-dev \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# instala Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

# copia seu código
COPY synapse /app

RUN pip install --upgrade pip

RUN pip install "prometheus_client<0.20"

# instala dependências corretas primeiro
RUN pip install "matrix-synapse[all]"

# depois sobrepõe com seu código
COPY synapse /app
RUN pip install -e /app

EXPOSE 3000

CMD ["python", "-m", "synapse.app.homeserver", "--config-path", "/data/homeserver.yaml"]
