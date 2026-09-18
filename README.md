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
mounted SQLite file or a Postgres server instead. For Postgres, put both
containers on the same Docker network so they can reach each other by name:

```bash
docker network create next-in-dining-net

docker run -d --name next-in-dining-db \
  --network next-in-dining-net \
  -e POSTGRES_USER=nid \
  -e POSTGRES_PASSWORD=nid \
  -e POSTGRES_DB=nid \
  -v next-in-dining-pgdata:/var/lib/postgresql/data \
  postgres:16-alpine

docker run --rm -p 8000:8000 \
  --network next-in-dining-net \
  -e DATABASE_URL=postgresql://nid:nid@next-in-dining-db:5432/nid \
  --name next-in-dining next-in-dining:latest
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
