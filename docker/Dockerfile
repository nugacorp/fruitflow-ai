# Imagen base compartida por backend, bot y worker.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev curl tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY telegram_bot ./telegram_bot
COPY worker ./worker
COPY prompts ./prompts
COPY sql ./sql

RUN pip install --upgrade pip && pip install -e ".[media]"

RUN useradd -m -u 1000 fruitflow && chown -R fruitflow:fruitflow /app
USER fruitflow

# ---- backend ----
FROM base AS backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1
CMD ["uvicorn", "backend.interfaces.http.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- bot ----
FROM base AS bot
CMD ["python", "-m", "telegram_bot.main"]

# ---- worker ----
FROM base AS worker
CMD ["celery", "-A", "worker.celery_app", "worker", "-B", "-l", "info"]
