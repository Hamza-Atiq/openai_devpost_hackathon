FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.4.30 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system crickops \
    && useradd --system --gid crickops --create-home crickops

WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev \
    && chown -R crickops:crickops /app

USER crickops
EXPOSE 8080

CMD ["uv", "run", "--directory", "apps/api", "python", "-m", "app.deployment.runtime", "serve"]

