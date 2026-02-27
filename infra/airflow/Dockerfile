FROM apache/airflow:2.9.3-python3.10

USER root

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.cargo/bin/uv /usr/local/bin/uv

USER airflow

WORKDIR /app

COPY --chown=airflow:root pyproject.toml uv.lock* ./

RUN uv sync
RUN uv cache clean
