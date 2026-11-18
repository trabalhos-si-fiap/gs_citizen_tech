# syntax=docker/dockerfile:1
# Imagem única do backend, usada por três containers com funções distintas:
#   api        -> uvicorn (CMD padrão)
#   worker     -> python -m app.infrastructure.worker
#   db-migrate -> python -m app.infrastructure.migrations
ARG PYTHON_IMAGE=python:3.12.16-slim-trixie

# ---- builder: resolve dependências em um virtualenv isolado ----
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-compile -r /tmp/requirements.txt \
    && find /opt/venv -name '__pycache__' -prune -exec rm -rf {} + \
    && rm -rf /opt/venv/lib/python*/site-packages/pip* \
              /opt/venv/lib/python*/site-packages/setuptools*

# ---- runtime: só o virtualenv e o código, usuário sem privilégios ----
FROM ${PYTHON_IMAGE} AS runtime
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PHOTO_STORAGE_DIR=/app/var/photos
# Aplica correções de segurança do Debian publicadas após a imagem base.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home \
               --home-dir /nonexistent --shell /usr/sbin/nologin app \
    && rm -rf /usr/local/lib/python*/ensurepip
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
# Código pertence ao root: o processo da aplicação só consegue ler.
COPY app ./app
COPY db ./db
RUN mkdir -p /app/var/photos && chown app:app /app/var/photos
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "app.healthcheck", "api"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
