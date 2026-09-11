FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_TIMEOUT=30 \
    PIP_RETRIES=3 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt requirements.lock ./

RUN set -eux; \
    while IFS= read -r requirement; do \
        case "$requirement" in \
            ""|\#*) continue ;; \
        esac; \
        python -m pip install \
            --no-cache-dir \
            --disable-pip-version-check \
            --timeout "$PIP_TIMEOUT" \
            --retries "$PIP_RETRIES" \
            --no-deps \
            "$requirement"; \
    done < requirements.lock

COPY . .

RUN rm -rf .pytest_cache __pycache__ tests venv .env \
    && useradd --system --uid 10001 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R 10001:10001 /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
