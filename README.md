# Next in Dining Application

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

The backend stores data in SQLite (`backend/waitlist.db` by default) via
SQLAlchemy. On first run it seeds a demo host account
(`host@waitlist.test` / `host1234`) and a few sample waitlist parties;
data then persists across restarts. To point it at a different database,
including Postgres, set `DATABASE_URL`:

```bash
DATABASE_URL="sqlite:///./somewhere-else.db" make run
DATABASE_URL="postgresql://nid:nid@localhost:5432/nid" make run
```

### Frontend (Vite + React, `frontend/`)

```bash
cd frontend
npm install    # first time only
npm run dev    # starts the app on http://localhost:5173
```

The frontend talks to the backend at the URL in `VITE_API_BASE_URL`, which
defaults to `http://localhost:8000/v1` (see `.env.example`). Copy that file to
`.env` if you need to point it somewhere else.

## Running it with Docker

A single [Dockerfile](Dockerfile) builds the frontend with Node, then
copies the static output into a Python image that runs the backend, which
serves the frontend too - one container, one port.

```bash
docker build -t next-in-dining:latest .
docker run --rm -p 8000:8000 --name next-in-dining next-in-dining:latest
```

Open `http://localhost:8000` - the API is at `http://localhost:8000/v1`.

By default the database lives inside the container and is lost when it's
removed. Set `DATABASE_URL` (same as running locally) to point it at a
mounted SQLite file or a Postgres server instead.

### With Postgres, via Docker Compose

[docker-compose.yaml](docker-compose.yaml) runs the app alongside a
Postgres container, wired together over `DATABASE_URL` with the data
persisted in a volume:

```bash
docker compose up --build
```

The frontend is built to call the backend at a relative `/v1` (same origin),
so this works regardless of what host/port you expose it on. Only if
frontend and backend ever run on different origins, rebuild with
`--build-arg VITE_API_BASE_URL=https://api.example.com/v1`.

## Tests

```bash
cd backend && make test
cd frontend && npm test
```

`backend/tests/integration/` runs the app against a real
[docker-compose.yaml](docker-compose.yaml) stack (build, Postgres,
static-frontend serving) instead of the in-memory SQLite used by
`make test`. It's excluded from the default run since it needs Docker;
run it explicitly with:

```bash
cd backend && make test-integration
```
