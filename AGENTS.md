Restaurant Waitlist Manager (Next in Dining): a real-time queue management
app for single-location restaurants. A host queue board manages walk-in
parties through a state machine; a public guest status page tracks live
queue position. `backend/` is a FastAPI REST API; `frontend/` is a Vite +
React SPA that talks to it through one services layer.

Documents

- `openapi.yml` - the API contract; every backend route implements exactly
  one operation in here, field-for-field (including camelCase JSON keys)
- `docs/spec.md` - the full product spec: user flows, the state engine
  table (section 7), data model, permissions matrix, token lifecycle
- `README.md` - how to run both halves

Commands

Backend (from `backend/`):
- `make install` - create `.venv` and install dependencies (first time only)
- `make run` - dev server with auto-reload on `http://localhost:8000`
- `make test` - the whole suite (`.venv/bin/pytest`)
- `.venv/bin/pytest tests/test_waitlist.py::test_name` - one test
- `make clean` - remove `.venv` and cached files

Frontend (from `frontend/`):
- `npm install` - install dependencies (first time only)
- `npm run dev` - dev server on `http://localhost:5173`
- `npm test` - the whole suite (`vitest run`); `npm run test:watch` to watch
- `npm run lint` - oxlint
- `npm run build` - typecheck (`tsc -b`) then production build

Rules

- The backend persists to a real database via SQLAlchemy, pointed at by the
  `DATABASE_URL` env var (default `sqlite:///./waitlist.db`, a file in
  `backend/`). Data survives restarts; seeding only happens once, on an
  empty database (`Store.__init__`), so don't assume a clean slate on every
  boot the way `store.reset()` (test-only) still gives you.
- Code in `app/store.py` and `app/db_models.py` must stay dialect-agnostic:
  no SQLite-specific SQL or types outside `app/db.py`'s `_create_engine`
  (which isolates the `check_same_thread`/`StaticPool` handling
  `sqlite:///:memory:` needs). Postgres is supported via `DATABASE_URL`
  alone (e.g. `postgresql://user:pass@host:5432/dbname`) - `_create_engine`
  already routes any non-SQLite URL through a plain `create_engine(url)`,
  so no code change was needed, only the `psycopg2-binary` driver
  dependency in `pyproject.toml`.
- No WebSocket gateway is implemented. `openapi.yml`'s `info.description`
  documents a `wss://.../waitlist/ws` channel, but that's out of scope for
  "implements the OpenAPI spec" - the spec itself only defines REST paths.
  The frontend's `RestWaitlistService.onHostQueueUpdate`/`onGuestUpdate`
  poll the matching `GET` endpoint every 3s instead of holding a socket
  open. Don't build a WS server without checking whether the frontend
  should switch from polling to it as part of the same change.
- Backend dependencies are managed with a plain `venv` + `pip`
  (`pyproject.toml` + `make install`), not `uv` - unlike `chore-tool` in
  this workspace, `uv` isn't installed in this environment. Add a new
  dependency to `pyproject.toml`'s `dependencies`/`optional-dependencies`,
  then re-run `make install`.
- No linter is configured for the backend. The frontend uses `oxlint`
  (`npm run lint`) - run it after any frontend change.
- Every backend call the frontend makes goes through
  `src/services/IWaitlistService.ts`, resolved via `useWaitlistService()`
  (`ServiceProvider`). Components and hooks never call `fetch` or a
  concrete service class directly - that's how the mock/real swap stays a
  one-line change instead of a rewrite.
- Host and guest bearer tokens are never interchangeable, and the guest
  token is sent as an `Authorization: Bearer` header rather than a URL path
  segment specifically so it doesn't get repeated in server access logs -
  even though the frontend also embeds it in the shareable
  `/status/:token` page URL.

Architecture

- **`CamelModel` (`app/models.py`)**: every backend schema is a Pydantic
  model with snake_case fields and an `alias_generator` that produces the
  spec's camelCase JSON keys (`party_size` -> `partySize`), with
  `populate_by_name=True` so either spelling parses on input. This is what
  keeps the Python code idiomatic while matching `openapi.yml` exactly on
  the wire - don't hand-roll aliases per field.
- **State machine (`app/store.py`)**: `TRANSITIONS` maps
  `{state: {action: next_state}}` per spec section 7.
  `Store.update_party_state()`/`cancel_party()` are the only two mutation
  paths that change a party's `state`, and both raise typed `StoreError`
  subclasses (`PartyNotFoundError` -> 404, `InvalidTransitionError` -> 409)
  rather than returning error values. A global handler in `app/main.py`
  converts those (and `HTTPException`s carrying a `{code, message}` dict
  detail) into the spec's flat `Error` body - FastAPI's default
  `{"detail": ...}` wrapper is intentionally overridden there.
- **Guest token expiry is computed at read time**, not via a background
  job: a `WAITING` party's token expires 12h after `createdAt`; a resolved
  party's (`SEATED`/`CANCELLED`/`NO_SHOW`) expires 2h after `resolvedAt`
  (`Store._is_guest_token_expired`, spec section 13). There's no cleanup
  sweep - an expired token just starts failing lookups.
- **`Store` (`app/store.py`) opens one DB session per method call**
  (`with db.SessionLocal() as session:`), commits, and converts ORM rows to
  plain Pydantic/dataclass values *before* the session closes - there's no
  FastAPI `Depends(get_db)` request-scoped session. This keeps every router
  and `app/auth.py` call site unchanged from the in-memory version; it's a
  deliberate simplicity trade-off for an app this size; introduce a
  per-request session only if a route needs several store calls to share
  one transaction.
- **Peak queue depth is its own table** (`ShiftMetricsRow`, one row,
  id=1), not derived from current party states - a party that contributed
  to the historical peak may have since moved to a different state, so the
  peak has to be persisted as a running counter (`Store._update_peak`,
  called after every mutation that could raise it).
- **Datetimes round-trip through SQLite as naive**, even though the code
  only ever writes `datetime.now(timezone.utc)`. `Store._as_utc` reattaches
  UTC tzinfo on every read (`_party_from_row`, guest-token expiry checks) -
  it's a no-op on dialects (e.g. Postgres) that preserve tzinfo natively, so
  don't remove it when adding another backend.
- **`app/auth.py` imports `app.store` lazily**, inside each dependency
  function body rather than at module level. `store.py` imports `auth.py`'s
  password-hashing functions at module level; a top-level import the other
  way would be circular. Password hashes use `bcrypt` directly (no
  `passlib`); tokens are opaque `secrets.token_urlsafe(32)` strings, not
  JWTs - there's nothing to decode, only a server-side map to look up.
- **CORS is wide open** (`allow_origins=["*"]` in `app/main.py`) because
  auth is bearer-token-based, not cookie-based - there's no CSRF surface
  that wildcard origins would expose. If cookie auth is ever added, this
  needs to become an explicit origin allowlist first.
- **`RestWaitlistService` (`frontend/src/services/restWaitlistService.ts`)**
  keeps the host bearer token as private instance state, set in `login()`
  and cleared in `logout()`, because `IWaitlistService`'s host-scoped
  methods (`getActiveParties`, `updatePartyState`) don't take a token
  parameter - only `login`/`logout` do the handshake. Guest-scoped methods
  take the guest token as an explicit argument on every call instead,
  because the guest token - not a stored session - is the frontend's only
  handle on that party.
- **Two `IWaitlistService` implementations** coexist by design:
  `MockWaitlistService` (fully in-memory, no network) and
  `RestWaitlistService` (the one described above). `ServiceProvider`
  defaults to `RestWaitlistService`; pass a different `service` prop (as
  the mock's own tests and any future component tests should) to swap it.
  `VITE_API_BASE_URL` (see `.env.example`) points `RestWaitlistService` at
  the backend, defaulting to `http://localhost:8000/v1`.
- **Tests**: backend tests live in `backend/tests/` (pytest + FastAPI's
  `TestClient`). `conftest.py` sets `DATABASE_URL=sqlite:///:memory:`
  *before* importing `app.main` (env var is read once, at `app/db.py`
  import time) so tests never touch the dev database file; the `client`
  fixture's `store.reset()` then drops and recreates every table before
  each test so state doesn't leak between them. Frontend service
  tests live in `src/services/__tests__/`, one file per implementation
  (`mockWaitlistService.test.ts`, `restWaitlistService.test.ts`); the REST
  one mocks `fetch` directly with `vi.stubGlobal` since no MSW or similar
  is set up in this project. `backend/tests/integration/` is a separate
  suite, marked `integration` and excluded from `make test`'s default
  `addopts` (`pyproject.toml`) since it drives `docker-compose.yaml` with
  real subprocess calls and hits the running stack over HTTP with `httpx`
  instead of `TestClient` - run it with `make test-integration`.
