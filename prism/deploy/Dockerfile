# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm
WORKDIR /app/prism
COPY prism/pyproject.toml ./
COPY prism/src ./src
COPY prism/scripts ./scripts
RUN --mount=type=secret,id=system_ca \
    set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends chromium fonts-noto-cjk nodejs ca-certificates; \
    if [ -f /run/secrets/system_ca ]; then export PIP_CERT=/run/secrets/system_ca; fi; \
    pip install --no-cache-dir '.[operations]'; \
    useradd --uid 10001 --create-home prism; \
    mkdir /data; chown prism:prism /data; chmod -R a+rX /app/prism; \
    rm -rf /var/lib/apt/lists/*
USER prism
ENV PYTHONUNBUFFERED=1
VOLUME /data
ENTRYPOINT ["python", "scripts/prism_operations.py", "--data", "/data"]
CMD ["worker", "--config", "/config/jobs.json"]
