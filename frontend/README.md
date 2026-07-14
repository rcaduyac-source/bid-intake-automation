# Byrdson Bid Intake — Frontend

React + Vite UI wired to the FastAPI backend.

## Local development

1. Start the backend (and DBs) first — see `../backend/README.md`.
2. From `frontend/`:

```bash
npm install
npm run dev
```

Vite proxies `/api` → `http://localhost:8000`. Open http://localhost:5173.

Optional: set `VITE_API_URL=http://localhost:8000` in `.env` to call the backend directly (CORS must allow the origin).

## Docker

Requires the shared network and running backend stack:

```bash
cd ../backend && docker compose up -d --build   # creates bid-intake-net
cd ../frontend && docker compose up -d --build  # joins bid-intake-net
```

Frontend: http://localhost:5173 (nginx proxies `/api` to `backend:8000`).
