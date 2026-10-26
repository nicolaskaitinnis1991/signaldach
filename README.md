# SignalDACH — AI-Powered Crypto Market Intelligence for DACH

> **📦 Archived project (April 2026).** SignalDACH was built in April 2026 on the thesis
> that MiCA licensing would open a market window for regulatory-aware crypto market
> intelligence in Germany, Austria and Switzerland. A follow-up market review in
> October 2026 confirmed the regulatory read was correct — and that the window was
> absorbed by incumbents: 100+ licensed institutions in Germany alone (including 41
> banks authorized in a single quarter) and established tooling covering the parts.
> The code is released as-is under the MIT license: a complete, tested,
> self-hostable snapshot of a production-grade build — kept public as proof of an
> early, correct market read. It is not maintained and will not accept issues or PRs.

Real-time market data, signal analysis, paper trading, tax calculation, and compliance monitoring for cryptocurrency funds operating in the DACH region (Germany, Austria, Switzerland).

## Features

- **Live Market Data** — CoinGecko, DefiLlama, Binance, Fear & Greed Index (auto-updating)
- **AI Signal Engine** — Composite signals from sentiment, technical, on-chain, and regulatory agents
- **17 Dashboard Pages** — Executive, Market, Signals, Fund, Paper Trading, Tax, Compliance, Chat, Reports, etc.
- **Paper Trading** — HNW risk limits (125K EUR min capital, max 25% position, 15% drawdown)
- **Tax Calculator** — DACH-specific (DE/AT/CH separate rules)
- **MiCA/DORA Compliance** — 7 regulatory documents
- **i18n** — German, English, French, Spanish
- **119 RSS Sources** — BaFin, FINMA, CoinDesk, CoinTelegraph, Reddit, Telegram
- **Observability** — Grafana (12 panels), Prometheus alerting (6 rules)

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Next.js 16     │────▶│   FastAPI         │────▶│  PostgreSQL 16   │
│   Frontend       │     │   Backend         │     │  + TimescaleDB   │
│   (Vercel)       │     │   (Railway)       │     │                  │
└──────────────────┘     └────────┬─────────┘     └──────────────────┘
                                  │
                          ┌───────┴────────┐
                          │   Redis 7      │
                          │   Cache + PubSub│
                          └────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
              CoinGecko     DefiLlama      Binance
              BaFin RSS     FINMA News     119 Sources
```

## Quick Start (Docker Compose)

**One command to run everything:**

```bash
# 1. Clone the repo
git clone https://github.com/nicolaskaitinnis1991/signaldach.git
cd signaldach

# 2. Copy environment files
cp backend/.env.example backend/.env

# 3. Start all services (PostgreSQL, Redis, Backend, Frontend)
docker compose up --build
```

Open:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

**Optional — ML-based German sentiment (adds ~6 GB of torch/CUDA wheels; without it the pipeline uses its built-in lexicon):**
```bash
docker compose build --build-arg INSTALL_ML=true backend
```

**With monitoring (Grafana + Prometheus):**
```bash
docker compose --profile monitoring up --build
```
- **Grafana**: http://localhost:3030 (admin / signaldach_dev)
- **Prometheus**: http://localhost:9090

## Local Development (without Docker)

### Backend
```bash
cd backend
cp .env.example .env          # Edit with your API keys
pip install -e ".[dev]"       # Install dependencies
python -m alembic upgrade head # Run migrations
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

### Run Tests
```bash
# Backend — verified 2026-10: 333 passed, 17 skipped (skips need live Redis / external APIs)
cd backend && python -m pytest -v

# Frontend — verified 2026-10: 20/20
cd frontend && npm test
```

## Production Deployment

### Railway (Backend)

1. Create a new Railway project
2. Add **PostgreSQL** and **Redis** services
3. Deploy backend from this repo's `backend/` directory
4. Set environment variables:

| Variable | Value |
|---|---|
| `SIGNALDACH_ENV` | `production` |
| `SIGNALDACH_DATABASE_URL` | `postgresql://...` (from Railway PostgreSQL) |
| `SIGNALDACH_REDIS_URL` | `redis://...` (from Railway Redis) |
| `SIGNALDACH_JWT_SECRET_KEY` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SIGNALDACH_CORS_ORIGINS` | `https://your-frontend.vercel.app` |
| `SIGNALDACH_AUTH_ENABLED` | `true` |
| `SIGNALDACH_OPENAI_API_KEY` | (optional, falls back to rule-based) |
| `SIGNALDACH_ANTHROPIC_API_KEY` | (optional) |

### Vercel (Frontend)

1. Import `frontend/` directory in Vercel
2. Set environment variable:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | `https://your-backend.railway.app` |

## Environment Variables Reference

See [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example) for all available configuration options.

## Default Login

After first startup, create a user via API:
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@signaldach.com", "password": "YourSecurePassword123!"}'
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, Recharts, SWR, Zustand |
| Backend | FastAPI, Gunicorn, Uvicorn, Pydantic |
| Database | PostgreSQL 16 + TimescaleDB (dev: SQLite) |
| Cache | Redis 7 (LRU, Pub/Sub, Streams) |
| AI | FinBERT, Claude/GPT (optional), rule-based fallback |
| Auth | JWT (NIST 800-63B password policy, account lockout) |
| Monitoring | Prometheus, Grafana, Sentry |
| CI/CD | GitHub Actions, Docker, Railway, Vercel |

## License

MIT — see [LICENSE](LICENSE).
