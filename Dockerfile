FROM python:3.12-slim

# Parches de seguridad del sistema operativo (openssl, glibc, zlib, ...).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project --extra fast

COPY App ./App
RUN uv sync --locked --no-dev --extra fast

# La app no necesita privilegios: corre con un usuario sin root.
RUN useradd --system --uid 10001 --no-create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "App.main:app", "--host", "0.0.0.0", "--port", "8000"]
