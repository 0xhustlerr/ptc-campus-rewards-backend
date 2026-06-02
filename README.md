# PTC Campus Rewards API

Closed-loop campus **PTC Credits** wallet for PTC barber college. Students earn and redeem PTC Credits on campus only — no blockchain, external transfers, cash-out, or student-to-student transfers.

## Stack

- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL (ledger source of truth)
- In-house OAuth 2.0 (JWT access + refresh tokens)
- Celery + Redis (background jobs + beat)
- Docker / AWS EC2 ready

## Local setup

### With Docker

```bash
cd backend
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed
```

- API: http://localhost:8000/docs
- Health: `GET /health`, `GET /api/v1/health`

### Without Docker

Run the API on your machine with local (or separately hosted) PostgreSQL and Redis.

**Prerequisites**

- Python 3.12+
- PostgreSQL 16+ with database `ptc_rewards` and user matching `.env` (defaults: user `ptc`, password `ptc_secret`)
- Redis 7+ on `localhost:6379`

If you only want Postgres and Redis in containers, start them and keep the API native:

```bash
cd backend
docker compose up db redis -d
```

**Setup**

```bash
cd backend
cp .env.example .env
# Edit .env if your Postgres/Redis hosts or credentials differ

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed
```

Create the database once (if it does not exist), for example:

```bash
psql -U postgres -c "CREATE USER ptc WITH PASSWORD 'ptc_secret';"
psql -U postgres -c "CREATE DATABASE ptc_rewards OWNER ptc;"
```

**Run the API**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API: http://localhost:8000/docs
- Health: `GET /health`, `GET /api/v1/health`

**Optional — Celery** (separate terminals, same venv and `.env`):

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

The API and auth flows work without Celery; background jobs and scheduled tasks need worker + beat.

## Commands

| Task | Command |
|------|---------|
| Migrations | `alembic upgrade head` |
| New migration | `alembic revision --autogenerate -m "description"` |
| Seed (rules, catalog, dev users) | `python -m scripts.seed` |
| Seed dev logins only | `python -m scripts.seed_users` |
| Tests | `pytest` |
| Celery worker | `celery -A app.workers.celery_app worker --loglevel=info` |
| Celery beat | `celery -A app.workers.celery_app beat --loglevel=info` |

## Frontend connection

```env
# frontend/.env.local
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_USE_MOCK_API=false
```

Attach JWT: `Authorization: Bearer <access_token>` from `POST /api/v1/auth/login`.

### Dev login accounts (after `python -m scripts.seed_users`)

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@ptc.edu` | `CampusDev123!` |
| Staff | `staff@ptc.edu` | `CampusDev123!` |
| Student | `student@ptc.edu` | `CampusDev123!` |
| Vendor | `vendor@ptc.edu` | `CampusDev123!` |

Local development only — do not use these credentials in production.

## Auth endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/login` | Email + password → tokens |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Revoke refresh token |
| POST | `/api/v1/auth/register` | Admin creates user |
| GET | `/api/v1/auth/me` | Current user |

## RBAC

| Role | Access |
|------|--------|
| student | Own wallet, QR session, transactions |
| staff | Issue PTC Credits, list students |
| vendor | Scan QR, redeem vendor items |
| admin | Full access, reports, adjustments |

Dependencies: `get_current_user`, `require_role`, `require_any_role`.

## QR sessions

- `POST /api/v1/wallets/me/qr-session` — student generates 60s opaque token (hash stored only)
- `POST /api/v1/vendor/scan` — validate session, return display name + balance
- `POST /api/v1/vendor/redeem` — single-use redemption with receipt

## Admin reports

- `GET /api/v1/admin/reports/overview`
- `GET /api/v1/admin/reports/token-velocity`
- `GET /api/v1/admin/reports/earned-by-rule`
- `GET /api/v1/admin/reports/redeemed-by-category`
- `GET /api/v1/admin/reports/top-students`
- `GET /api/v1/admin/reports/vendor-summary`

## Celery jobs

| Task | Schedule |
|------|----------|
| `weekly_perfect_attendance_bonus` | Monday 06:00 UTC |
| `daily_token_activity_summary` | Daily 23:30 UTC |
| `expire_old_qr_sessions` | Every 15 min |
| `generate_admin_metrics_snapshot` | Daily 00:05 UTC |

## Production (AWS EC2)

1. Copy `deploy/` examples and `.env.production.example` → `.env.production`
2. `docker compose -f docker-compose.prod.yml up -d`
3. `docker compose -f docker-compose.prod.yml exec api alembic upgrade head`
4. `docker compose -f docker-compose.prod.yml exec api python -m scripts.seed`
5. Configure nginx (`deploy/nginx/ptc-rewards.conf`) + TLS (certbot)
6. Optional systemd units in `deploy/systemd/`

### Environment variables

See `.env.production.example` — required: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `BACKEND_CORS_ORIGINS`.

## Ledger

Balances are computed from double-entry `ledger_entries`. No mutable balance columns on wallets.

| Event | Debit | Credit |
|-------|-------|--------|
| Earn | `rewards_pool` | `student_wallet` |
| Redeem | `student_wallet` | `vendor_revenue` |
