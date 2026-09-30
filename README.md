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

## Deploying to Render

[render.yaml](render.yaml) is a [Render](https://render.com) Blueprint that
provisions two copies of the app, both built from the same
[Dockerfile](Dockerfile):

- `next-in-dining` - **production**, backed by a managed Postgres database
  over `DATABASE_URL`.
- `next-in-dining-dev` - **development**, where every push to `main` lands
  first. Render's free plan allows a single free Postgres, so dev runs on
  the default SQLite file, which is recreated (and re-seeded) on every
  deploy.

Render doesn't run `docker-compose.yaml` directly - that's for local dev -
the Blueprint is its cloud equivalent.

1. Push this repo (with `render.yaml`) to GitHub.
2. In the Render dashboard: **New +** → **Blueprint**, connect the repo,
   pick the `main` branch.
3. Render reads `render.yaml` and shows the plan - two web services, one
   Postgres. Review it and click **Apply**.
4. Once the build finishes, Render gives a public URL that serves both the
   frontend and the API at `/v1` (same origin, so no `VITE_API_BASE_URL`
   override is needed).

On the free plan, the web service sleeps after 15 minutes idle (the next
request takes ~30-50s to wake it), and the free Postgres instance expires
after 30 days.

### Continuous deployment (GitHub Actions)

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every push
and pull request: backend and frontend tests in parallel, then the
docker-compose-based integration and e2e suites, and - only on a push to
`main`, once everything else passed - deploys to **dev** and polls dev's
`/health` until it reports the pushed commit as its `version`. Production
is never deployed by a push.

`render.yaml` sets `autoDeploy: false`, so Render *only* deploys when this
pipeline tells it to - a push alone no longer triggers one. That requires
these repository settings (Settings → Secrets and variables → Actions),
each taken from the matching service in the Render dashboard:

- Secrets `RENDER_DEV_DEPLOY_HOOK_URL` / `RENDER_PROD_DEPLOY_HOOK_URL` -
  the service's Settings → Deploy Hook.
- Variables `RENDER_DEV_URL` / `RENDER_PROD_URL` - the service's public
  URL (e.g. `https://next-in-dining.onrender.com`), used to poll `/health`.

### Promoting to production

[.github/workflows/promote.yml](.github/workflows/promote.yml) is the only
way production changes. Run it by hand from Actions → **Promote to
production** → Run workflow, tick the confirmation checkbox, and
optionally give a commit SHA (by default it promotes whatever dev's
`/health` reports as its `version`). It checks the commit is on `main`,
waits for approval on the `production` environment, deploys exactly that
commit to production (Render's deploy hook with `&ref=<sha>`), and polls
production's `/health` until it reports that version.

One-time setup in Settings → Environments: create `production` with
yourself as a **Required reviewer**, and keep the
`RENDER_PROD_DEPLOY_HOOK_URL` secret there so only an approved job can
deploy to production.

## Tests

```bash
cd backend && make test
cd frontend && npm test
```

`GET /health` (a trivial DB round-trip, separate from `/`) returns the
`environment` (`APP_ENV`) and deployed `version` (`APP_VERSION`, else
Render's `RENDER_GIT_COMMIT`). It's what
Render's health check and the CI pipeline poll after a deploy; it's
covered by `backend/tests/test_health.py`.

`backend/tests/integration/` runs the app against a real
[docker-compose.yaml](docker-compose.yaml) stack (build, Postgres,
static-frontend serving) instead of the in-memory SQLite used by
`make test`. It's excluded from the default run since it needs Docker;
run it explicitly with:

```bash
cd backend && make test-integration
```

`e2e/` is a separate [Playwright](https://playwright.dev) suite that also
drives the `docker-compose.yaml` stack, but through a real browser instead
of HTTP calls: a host signs in in one browser session while a guest joins
the waitlist from a separate one, and the test confirms the host's queue
board picks up the new party live (via the existing 3s poll), without a
page reload. First time only, install its dependencies and browser:

```bash
cd e2e
npm install
npx playwright install --with-deps chromium
```

Then run it (builds and tears down the Docker stack automatically):

```bash
cd e2e && npm test
```
