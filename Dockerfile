# Imagen única para los dos servicios que corren código Django: `web`
# (gunicorn) y `worker` (celery). Cada uno define su propio `command` en
# docker-compose.yml; esta imagen no tiene CMD fijo.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Deps de sistema: mysqlclient necesita compilar contra libmysqlclient,
# pyzbar necesita el binario nativo de zbar, curl lo usa el healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-libmysqlclient-dev \
        pkg-config \
        build-essential \
        libzbar0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
