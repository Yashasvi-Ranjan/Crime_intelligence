# syntax=docker/dockerfile:1
# Cross-Station Crime Intelligence API  (docker build -t crime-intel . && docker run -p 8000:8000 crime-intel)

# ── stage 1: bundle the vendored Apache-2.0 Meterless reference engines (H-MEM, Markovian) ──
FROM node:20-slim AS engines
WORKDIR /src
COPY third_party ./third_party
COPY backend/app/services/meterless_world/reference ./backend/app/services/meterless_world/reference
COPY scripts/build_reference_engines.sh ./scripts/build_reference_engines.sh
RUN sh scripts/build_reference_engines.sh

# ── stage 2: runtime ──
FROM python:3.11-slim
# Node runs the Meterless engine runners (mounted Nightshift engines and the bundled references).
COPY --from=node:20-slim /usr/local/bin/node /usr/local/bin/node

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY run.py ./
COPY backend ./backend
COPY data/generated ./data/generated
COPY data/sample ./data/sample
COPY data/evaluation ./data/evaluation
COPY tests ./tests
COPY scripts ./scripts
COPY input_examples ./input_examples
COPY output_examples ./output_examples
COPY third_party/meterless/LICENSE third_party/meterless/NOTICE.md ./third_party/meterless/
COPY --from=engines /src/third_party/meterless/build ./third_party/meterless/build

# Defaults for a container that reaches Zetaris / Nightshift on the Docker HOST. Override with -e / --env-file.
# (The proprietary Nightshift engine directory is never in the image: mount it read-only at /opt/meterless/engine.)
ENV NIGHTSHIFT_BASE_URL=http://host.docker.internal:8088/v1 \
    ZETARIS_BASE_URL=http://host.docker.internal:8888 \
    ZETARIS_AUTH_URL=http://host.docker.internal:8889 \
    ZETARIS_JDBC_HOST=host.docker.internal \
    METERLESS_ENGINE_DIR=/opt/meterless/engine \
    METERLESS_WORLD_MODEL_PATH=/opt/meterless/engine/worldmodel.js \
    METERLESS_WORLD_DIR=/app/.state/world \
    STATE_DIR=../.state \
    PORT=8000

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/logs /app/.state /opt/meterless/engine \
    && chown -R app:app /app/logs /app/.state
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=4)" || exit 1
CMD ["python", "run.py"]
