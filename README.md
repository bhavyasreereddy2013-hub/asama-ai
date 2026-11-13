# ASAMA.ai

ASAMA.ai is a FastAPI business-networking MVP with local semantic discovery, business profiles and agents, opportunity posts, saved posts, connections, notifications, and direct messaging.

## Local development

Use Python 3.13 and run these commands from `backend`:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:APP_ENV = "development"
python -m uvicorn app.main:app --reload
```

In development, an empty database is seeded with sample businesses:

| Email | Password |
| --- | --- |
| `northstar@asama.ai` | `password123` |
| `harvest@asama.ai` | `password123` |
| `cobalt@asama.ai` | `password123` |

These accounts are for local development only. Production refuses to start with demo seeding enabled. The database defaults to `backend/asama.db`; override `DATABASE_URL` to use another SQLite file. The semantic model runs locally and is downloaded the first time a search is performed.

Run the backend tests with:

```powershell
python -m pytest -q
```

## Deployment preparation

The included Docker setup runs one Uvicorn process, persists the SQLite database and embedding cache in a named volume, runs as a non-root user, and binds to loopback. Put a TLS-terminating reverse proxy in front of it; do not expose the container port directly to the public internet.

From `backend`, copy `.env.example` to `.env`, generate a unique key, and put it in `JWT_SECRET_KEY`:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then set the generated value in `.env` and start the service:

```powershell
docker compose up --build -d
```

Check `http://127.0.0.1:8000/health`. Keep `.env` private and back up the `asama_data` volume. The first semantic search downloads the embedding model; subsequent runs use the persisted local cache.

Production mode requires `JWT_SECRET_KEY` and `DATABASE_URL`, requires a 32-byte minimum JWT key, disables sample-account seeding, and refuses to start if demo seeding is enabled. Start with a new production database; do not promote the local development database, which already contains the sample accounts. For non-container deployment, set `APP_ENV=production`, `JWT_SECRET_KEY`, `DATABASE_URL`, and `SEED_DEMO_DATA=false` in the process environment.

## MVP operational limits

- SQLite is configured for a small, single-instance deployment; use a planned migration before changing the database schema.
- The app creates missing tables at startup but does not yet include a schema migration system.
- Email verification and password recovery are not implemented.
- Review privacy, retention, and legal requirements before accepting real customer information. Business profiles and published posts are discoverable by other users.
- Configure TLS, backups, monitoring, and reverse-proxy request limits in the hosting environment.
