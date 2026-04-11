# Observaboard

Observability event ingestion and management platform. Accepts webhook events from any source, classifies them automatically, and provides a real-time dashboard for monitoring.

## Architecture

```
                   ┌──────────────┐
  Webhooks ──────► │  Django API  │ ──── POST /api/ingest/
                   │  (Gunicorn)  │
                   └──────┬───────┘
                          │
                    ┌─────▼─────┐
                    │   Redis   │  (Celery broker)
                    └─────┬─────┘
                          │
                   ┌──────▼───────┐
                   │ Celery Worker│ ── classify events
                   └──────┬───────┘
                          │
                   ┌──────▼───────┐
                   │  PostgreSQL  │  (events, search vectors)
                   └──────────────┘
```

**Tech stack:** Django 5.1 · Django REST Framework · Celery · PostgreSQL (full-text search) · Redis · HTMX · Tailwind CSS · Docker · Fly.io

## Features

- **Event ingestion** — REST API accepting webhooks with API key or JWT authentication
- **Auto-classification** — Celery tasks categorize events by type and severity
- **Full-text search** — PostgreSQL search vectors with relevance ranking
- **Dashboard** — Real-time web UI with stats, filtering, and event detail views
- **API key management** — Create, revoke, and monitor API keys
- **OpenAPI docs** — Interactive Swagger UI at `/api/docs/`
- **Rate limiting** — Scoped throttling on ingest and search endpoints

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Setup

```bash
# Clone and enter the project
git clone https://github.com/rodmen07/observaboard.git
cd observaboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set a real SECRET_KEY (required)

# Create database and run migrations
createdb observaboard
python manage.py migrate

# Create a superuser for the dashboard
python manage.py createsuperuser

# Start the development server
python manage.py runserver

# In a separate terminal, start the Celery worker
celery -A observaboard worker --loglevel=info
```

### Running Tests

```bash
pytest                  # run all tests
pytest --cov            # with coverage report
pytest -x               # stop on first failure
```

## API Reference

All API endpoints require authentication via `Authorization: Api-Key <key>` header or JWT bearer token, unless noted otherwise.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health/` | None | Health check (API, DB, Redis) |
| `POST` | `/api/ingest/` | Required | Ingest a webhook event |
| `GET` | `/api/events/` | Required | List events (filterable, paginated) |
| `GET` | `/api/events/<uuid>/` | Required | Get event detail |
| `GET` | `/api/events/search/?q=` | Required | Full-text search |
| `GET/POST` | `/api/keys/` | Admin | List/create API keys |
| `PATCH/DELETE` | `/api/keys/<id>/` | Admin | Update/delete API key |
| `POST` | `/api/auth/token/` | None | Obtain JWT token |
| `POST` | `/api/auth/token/refresh/` | None | Refresh JWT token |
| `GET` | `/api/docs/` | None | Swagger UI |
| `GET` | `/api/schema/` | None | OpenAPI schema |

### Ingest Payload

```json
{
  "source": "github",
  "event_type": "push",
  "payload": {
    "ref": "refs/heads/main",
    "message": "Merged PR #42"
  }
}
```

### Filter Parameters (GET /api/events/)

- `source` — filter by event source
- `category` — `deployment`, `security`, `alert`, `metric`, `info`
- `severity` — `low`, `medium`, `high`, `critical`
- `event_type` — filter by event type
- `classified` — `true` or `false`

## Dashboard

The web dashboard is available at `/dashboard/` and requires Django session authentication (login with your superuser account).

**Pages:**
- **Home** — Event counts by category and severity, recent events feed
- **Events** — Searchable, filterable event list with HTMX-powered pagination
- **Event Detail** — Full event view with formatted JSON payload
- **API Keys** — Admin-only key management (create, revoke, delete)

## Deployment

### Fly.io

```bash
# Set secrets
fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
fly secrets set DATABASE_URL=<your-postgres-url>
fly secrets set REDIS_URL=<your-redis-url>

# Deploy
fly deploy
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | — | Django secret key |
| `DEBUG` | No | `false` | Enable debug mode |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `DATABASE_URL` | No | — | PostgreSQL connection URL |
| `DB_NAME` | No | `observaboard` | Database name (if no DATABASE_URL) |
| `DB_USER` | No | `postgres` | Database user |
| `DB_PASSWORD` | No | `postgres` | Database password |
| `DB_HOST` | No | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `CORS_ALLOWED_ORIGINS` | No | — | Comma-separated CORS origins |
