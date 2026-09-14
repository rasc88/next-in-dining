# Restaurant Waitlist Manager

A real-time queue management app for single-location restaurants. Hosts manage
walk-in parties from a queue board; guests join via a public form and track
their live position. See [openapi.yml](openapi.yml) for the API contract and
[docs/spec.md](docs/spec.md) for the full product spec.

## Prerequisites

- Python 3.12+
- Node.js with npm

## Running it

Start the backend first, then the frontend, each in its own terminal.

### Backend (FastAPI, `backend/`)

```bash
cd backend
make install   # first time only: creates .venv, installs dependencies
make run       # starts the API on http://localhost:8000, with auto-reload
```

The backend uses an in-memory store, seeded with a demo host account
(`host@waitlist.test` / `host1234`) and a few sample waitlist parties.
Restarting it resets all data.

### Frontend (Vite + React, `frontend/`)

```bash
cd frontend
npm install    # first time only
npm run dev    # starts the app on http://localhost:5173
```

The frontend talks to the backend at the URL in `VITE_API_BASE_URL`, which
defaults to `http://localhost:8000/v1` (see `.env.example`). Copy that file to
`.env` if you need to point it somewhere else.

## Tests

```bash
cd backend && make test
cd frontend && npm test
```
