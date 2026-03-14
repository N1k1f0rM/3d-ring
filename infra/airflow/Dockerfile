FROM apache/airflow:2.9.3-python3.12

USER root

RUN apt-get update && apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/3DTopia/OpenLRM.git /opt/openlrm && \
    chown -R airflow:root /opt/openlrm

USER airflow

RUN cd /opt/openlrm && git checkout v1.1.1 && \
    pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH="/opt:${PYTHONPATH}"

WORKDIR /app

COPY --chown=airflow:root pyproject.toml uv.lock* ./

RUN uv pip install --no-cache-dir . && uv cache clean
