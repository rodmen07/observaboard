# --- Build stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /install /usr/local
COPY . .

ENV SECRET_KEY=build-only-collectstatic
RUN python manage.py collectstatic --noinput
ENV SECRET_KEY=

USER app

EXPOSE 8000

CMD ["gunicorn", "observaboard.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
