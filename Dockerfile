FROM python:3.12-slim

ARG TARGETARCH
ARG INSTALL_DEV=false
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client curl \
    && curl -fsSL "https://dl.min.io/client/mc/release/linux-${TARGETARCH}/mc" \
       -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY mcp_server ./mcp_server
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
COPY tests ./tests
RUN if [ "$INSTALL_DEV" = "true" ]; then pip install '.[dev,legacy]'; else pip install '.[legacy]'; fi
RUN chmod +x scripts/start.sh scripts/create_readonly_user.sh

EXPOSE 8000
ENTRYPOINT ["./scripts/start.sh"]
