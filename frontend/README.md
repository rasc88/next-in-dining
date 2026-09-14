# Restaurant Waitlist Manager

A React + TypeScript front end for the Restaurant Waitlist Manager spec.
The whole app runs against an **in-memory mock backend** — no server
required — with every backend call centralized in one services layer so
a real implementation can be swapped in later without touching any
component.

## Run it

```bash
npm install
npm run dev       # start the app
npm run test      # run the test suite
npm run build     # production build
```

Demo host login: `host@waitlist.test` / `host1234`
(the board starts pre-seeded with a couple of demo parties).

## Routes

| Path             | Who               | What                                   |
| ---------------- | ----------------- | --------------------------------------- |
| `/`              | Anyone            | Landing page, links to join / host login |
| `/join`          | Guest             | Public check-in form                    |
| `/status/:token` | Guest link holder | Live position, ready banner, cancel     |
| `/login`         | Host              | Email/password sign-in                  |
| `/host`          | Signed-in host    | Queue board with filters and actions    |

## The services layer

Everything that would hit a real backend goes through one interface:

```
src/services/
  types.ts               domain types (WaitlistParty, PartyState, ...)
  IWaitlistService.ts     the interface — every method maps to a REST
                          endpoint or WebSocket event from the spec
  mockWaitlistService.ts  in-memory implementation: enforces the state
                          machine, simulates latency, and uses a small
                          pub/sub in place of WebSockets
  ServiceProvider.tsx     React context that hands the active service
                          down the tree
```

Components and hooks never call `fetch` or open a socket directly —
they call `useWaitlistService()` and use the interface. To connect a
real backend:

1. Write `HttpWaitlistService implements IWaitlistService`, backed by
   real REST calls and a real WebSocket for `onHostQueueUpdate` /
   `onGuestUpdate`.
2. Pass an instance of it to `<ServiceProvider service={...}>` in
   `main.tsx`.

No page, hook, or component changes.

## Tests

- `src/services/__tests__/mockWaitlistService.test.ts` — the state
  machine (valid and invalid transitions), auth, join flow, guest
  position math, and the pub/sub subscriptions.
- `src/pages/__tests__/HostBoardPage.test.tsx` — rendering parties,
  filtering by category, dispatching actions.
- `src/pages/__tests__/GuestStatusPage.test.tsx` — live position
  display, reacting to a host action pushed through the subscription,
  and the guest self-cancel flow.

## Notes on scope

This implements the MVP flows from the spec (sections 5–9) with a
mock backend standing in for sections 10–13 (real persistence,
WebSocket gateway, VAPID push). Web Push is stubbed as a toggle that
calls `subscribePush()` — a real integration would request
`Notification` permission and register a `PushSubscription` before
calling it.
