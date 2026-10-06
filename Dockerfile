FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1
ENV DJ_ARTIFACT_STORAGE_DIR=/app/data/artifact_store

COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY app ./app
COPY frontend ./frontend
COPY alembic ./alembic
COPY alembic.ini README.md .env.example ./
RUN groupadd --gid 10001 dandoonjan && useradd --uid 10001 --gid 10001 --no-create-home dandoonjan \
    && chmod -R go-w /app/app /app/frontend /app/alembic \
    && chmod go-w /app/alembic.ini /app/README.md /app/.env.example /app/requirements-runtime.txt \
    && mkdir -p /app/data/artifact_store \
    && chown 10001:10001 /app/data/artifact_store \
    && chmod 0700 /app/data/artifact_store
USER 10001:10001

CMD ["python", "-m", "app.deployment_serve"]
