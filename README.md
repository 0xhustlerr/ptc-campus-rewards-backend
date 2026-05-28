# PTC Campus Rewards API

Closed-loop campus **PTC Credits** wallet for PTC barber college. Students earn and redeem PTC Credits on campus only — no blockchain, external transfers, cash-out, or student-to-student transfers.

## Stack

- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL (ledger source of truth)
- In-house OAuth 2.0 (JWT access + refresh tokens)
- Celery + Redis (background jobs + beat)
- Docker / AWS EC2 ready

## Local setup

```bash
cd backend
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed
```

- API: http://localhost:8000/docs
- Health: `GET /health`, `GET /api/v1/health`

## Commands

| Task | Command |
|------|---------|
| Migrations | `alembic upgrade head` |
| New migration | `alembic revision --autogenerate -m "description"` |
| Seed | `python -m scripts.seed` |
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
