# SignalDACH — Market Intelligence for Crypto Funds

Real-time regulatory tracking, market news, competitor monitoring, and sentiment analysis
for cryptocurrency funds operating in the DACH region (Germany, Austria, Switzerland).

## Architecture

```
Frontend (Next.js)  →  reads  →  PostgreSQL  ←  writes  ←  Backend (FastAPI)
     Vercel                       Railway                      Railway
                                                                 ↓
                                                  BaFin, FINMA, CoinDesk,
                                                  Twitter, Reddit, Telegram
                                                  OpenAI API (classification)
```

## Quick Start

### 1. Start the database
```bash
docker compose up -d db
```

### 2. Start the backend
```bash
cd backend
cp .env.example .env  # Edit with your API keys
python3 -m uvicorn app.main:app --reload --port 8000
```

### 3. Seed default sources
```bash
curl -X POST http://localhost:8000/sources/seed-defaults
```

### 4. Start the frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Data Sources

| Source | Type | Category | Frequency |
|--------|------|----------|-----------|
| BaFin RSS | RSS | Regulation | 30min |
| FINMA News | RSS | Regulation | 30min |
| CoinDesk | RSS | Market | 15min |
| CoinTelegraph | RSS | Market | 15min |
| r/cryptocurrency | Reddit | Sentiment | 5min |
| r/bitcoin | Reddit | Sentiment | 5min |
| r/Finanzen | Reddit | Sentiment | 15min |
| Twitter/X | API | Sentiment | 5min |
| Telegram Channels | Web | Market | 10min |

## AI Pipeline

Each scraped item passes through:
1. **Classification** → regulation / competition / market / sentiment
2. **Relevance Scoring** → 1-10 (keyword + LLM)
3. **Summarization** → 2-3 sentence AI summary
4. **Urgency Detection** → normal / high / breaking

Works with OpenAI API key. Falls back to rule-based processing without one.

## Deployment

- **Frontend**: Deploy `frontend/` to Vercel
- **Backend**: Deploy `backend/` to Railway (with Dockerfile)
- **Database**: Railway managed PostgreSQL

## Environment Variables

### Backend (.env)
```
SIGNALDACH_DATABASE_URL=postgresql://...
SIGNALDACH_OPENAI_API_KEY=sk-...
SIGNALDACH_TWITTER_BEARER_TOKEN=...
SIGNALDACH_REDDIT_CLIENT_ID=...
SIGNALDACH_REDDIT_CLIENT_SECRET=...
SIGNALDACH_RESEND_API_KEY=...
```

### Frontend (.env)
```
NEXT_PUBLIC_BACKEND_URL=https://your-backend.railway.app
```
