FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FRAUDSHIELD_HOME=/data PORT=8000
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.lock
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
COPY --from=web /web/dist ./apps/web/dist
COPY benchmark-results/research/summary.json /app/reference-benchmark.json
RUN useradd --uid 10001 --create-home app && mkdir -p /data && chown app:app /data
ENV FRAUDSHIELD_WEB_DIST=/app/apps/web/dist
ENV FRAUDSHIELD_REFERENCE_BENCHMARK=/app/reference-benchmark.json
ENV FRAUDSHIELD_DEPENDENCY_LOCK=/app/requirements.lock
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/ready', timeout=3)"
CMD ["sh", "-c", "exec python -m uvicorn fraudshield.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
