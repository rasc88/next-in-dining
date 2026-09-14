# Restaurant Waitlist Manager

## Product and Technical Specification — MVP v1.0

**Status:** Draft  
**Date:** September 14, 2026  
**Audience:** Product, Design, Engineering, QA, and Operations  

---

## 1. Product Summary

The **Restaurant Waitlist Manager** is a browser-based, real-time queue management workspace designed for single-location restaurants. It replaces paper sign-in logs and hardware pagers with a web interface for front-of-house hosts and a live status page for guests.

Hosts manage walk-in parties across mobile or desktop devices, track table availability, and trigger instant guest calls. Guests join via a public check-in link or host entry, track their live queue position, receive Web Push alerts when their table is ready, and self-cancel if plans change.

---

## 2. Goals

The MVP must:

1. Allow hosts to authenticate securely via email and password to manage active queues.
2. Provide a categorized list view for hosts to manage, filter, and transition guest states.
3. Allow guests to join via public web form or manual host entry.
4. Deliver low-latency (<1s p95) real-time position updates and table alerts over WebSockets.
5. Support browser Web Push Notifications for table alerts, with on-screen visual banners as fallback.
6. Enable guest self-cancellation directly from their live status page.
7. Support operational recovery actions (re-notify guest, un-seat party).
8. Capture basic performance metrics: active queue depth and peak hourly waiting volume.

---

## 3. Non-Goals for MVP

The following are intentionally excluded from the initial release:

- Automated wait-time estimation algorithms (only party counts are displayed).
- Multi-tenant SaaS architecture (built strictly for single-location operations).
- Interactive 2D floor plans or auto-assignment seating rules.
- Native mobile applications (iOS/Android) or SMS/WhatsApp fallback gateways.
- Point of Sale (POS) or external reservation system integrations (e.g., Toast, Square, OpenTable).
- Historical analytics beyond simple hourly peak volume.

---

## 4. Users and Roles

### 4.1 Host / Front-of-House Staff
An authenticated staff member who can:
- Authenticate via email and password.
- Manually create, view, filter, and manage guest queue entries.
- Transition guest states (`notified`, `seated`, `no_show`, `cancelled`, `un-seat`, `re-notify`).
- View real-time queue metrics (active waiting count, hourly volume).
- Clear or remove entries from the active board.

### 4.2 Guest / Diner
An unauthenticated or token-authorized visitor who can:
- Join the waitlist by entering Name, Phone Number, Party Size, and Seating Category via a public web form.
- View a personal, dynamic queue tracking URL containing position in line and total parties waiting.
- Grant Web Push Notification permissions for table ready alerts.
- Self-cancel their position in line.
- Receive immediate visual alerts on the status page when marked `notified`.

---

## 5. Core User Flows

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GUEST WAITLIST FLOW                             │
└────────────────────────────────────────────────────────────────────────┘

  [ Guest Check-In Web Form ]              [ Host Manual Entry Portal ]
              │                                         │
              └────────────────────┬────────────────────┘
                                   │
                                   ▼
                   ┌───────────────┴───────────────┐
                   │    State: WAITING             │
                   │    (WebSocket Connected)      │
                   └───────────────┬───────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             │ (Host "Notify")     │ (Guest "Cancel")    │ (Auto/Expiry)
             ▼                     ▼                     ▼
   ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐
   │  State: NOTIFIED  │  │ State: CANCELLED  │  │  State: EXPIRED   │
   └─────────┬─────────┘  └───────────────────┘  └───────────────────┘
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
┌───────────┐ ┌───────────┐
│  SEATED   │ │  NO_SHOW  │
└─────┬─────┘ └───────────┘
      │
      ▼ (Host "Un-seat" revert)
┌───────────┐
│  WAITING  │
└───────────┘
```

### 5.1 Joining the Queue
1. **Self Entry:** Guest accesses public web page, fills out entry form (Name, Phone, Party Size, Seating Category), and submits.
2. **Host Entry:** Alternatively, Host enters guest details directly on the host portal.
3. System assigns a secure token, creates a `WAITING` party record, and opens a WebSocket session with the guest device.
4. Guest is prompted for Web Push permission.

### 5.2 Live Status & Notification
1. Guest page maintains a WebSocket connection showing current queue position (e.g., "3 parties ahead of you").
2. Host filters the queue by category and clicks **Notify**.
3. State transitions to `NOTIFIED`. System fires a Web Push Notification and pushes an instant WebSocket event.
4. Guest status page updates immediately with a prominent visual banner ("Your table is ready!").

### 5.3 Resolution & Recovery
1. When guest arrives at host stand, Host clicks **Seat** (state -> `SEATED`).
2. If guest does not respond, Host clicks **No-Show** (state -> `NO_SHOW`).
3. If guest clicks **Cancel** on status page, state transitions to `CANCELLED` and Host board updates.
4. **Recovery Actions:** Host may click **Re-Notify** on a `NOTIFIED` party to resend alerts, or **Un-seat** a `SEATED` party to revert them back to `WAITING`.

---

## 6. Functional Requirements

### 6.1 Authentication & Host Access
- Host authentication via email and password using secure session tokens.
- Automatic logout after period of inactivity.

### 6.2 Host Queue Board
- Responsive layout optimized for mobile and desktop web browsers.
- Category tabs/filters (e.g., Indoor, Outdoor, High-top, Bar).
- One-click state controls (`Notify`, `Seat`, `No-Show`, `Cancel`, `Re-Notify`, `Un-Seat`).
- Active metrics banner showing total waiting parties and peak hourly volume.

### 6.3 Guest Status Page & Web Push
- Dynamic web page displaying current position in line and total queue depth.
- Web Push Notification integration via VAPID keys.
- Visual status banner on guest status page serving as a fallback if push notifications are denied.
- Interactive "Cancel My Spot" action with confirmation prompt.

---

## 7. Operational State Engine

| Current State | Allowed Action | Next State | Triggered Event |
| :--- | :--- | :--- | :--- |
| **None** | Create Entry | `WAITING` | Broadcast `queue_updated` to Host; Init Guest WS |
| `WAITING` | Host Clicks "Notify" | `NOTIFIED` | Send Web Push + WS event `table_ready` |
| `WAITING` | Guest Clicks "Cancel" | `CANCELLED` | Broadcast `queue_updated` to Host |
| `WAITING` | Inactivity Timeout | `EXPIRED` | System auto-cleanup |
| `NOTIFIED` | Host Clicks "Seat" | `SEATED` | Broadcast `queue_updated`; start token expiry timer |
| `NOTIFIED` | Host Clicks "No-Show" | `NO_SHOW` | Broadcast `queue_updated`; start token expiry timer |
| `NOTIFIED` | Host Clicks "Re-Notify" | `NOTIFIED` | Resend Web Push + WS event `table_ready` |
| `SEATED` | Host Clicks "Un-Seat" | `WAITING` | Re-insert party into active queue board |

---

## 8. UX Layout & Responsive Design

- **Host Interface:** Header bar with auth status and active metric counts. Main body containing filter chips, search input, and a categorized card/table list view with quick action buttons.
- **Guest Status View:** Clean, high-contrast single-column display showing party name, visual queue position card, status banner, push subscription toggle, and cancellation button.

---

## 9. Permissions Matrix

| Capability | Authenticated Host | Guest (Token Holder) | Public / Unauthenticated |
| :--- | :---: | :---: | :---: |
| Access Host Board & Metrics | **Yes** | No | No |
| Join Waitlist via Public Form | **Yes** | **Yes** | **Yes** |
| View Own Live Status Page | **Yes** | **Yes** | No |
| Change Party State (Notify/Seat/No-Show) | **Yes** | No | No |
| Re-Notify / Un-Seat Party | **Yes** | No | No |
| Cancel Own Reservation | **Yes** | **Yes** | No |

---

## 10. Technical Architecture

### 10.1 Stack Architecture
- **Frontend:** Responsive Single-Page Application (SPA) in TypeScript.
- **Backend API:** Node.js / TypeScript REST API for authentication and session creation.
- **Real-Time Gateway:** WebSocket server handling bidirectional real-time state synchronization.
- **Push Notification Service:** Web Push Protocol (VAPID) service worker integration.

### 10.2 Storage Layer
- **Relational / Document Storage:** Stores host credentials, active waitlist items, and historical event logs. Phone numbers are maintained in plain text per operational requirements.
- **In-Memory Store:** Tracks active WebSocket connections and subscription channels.

---

## 11. Data Model

### HostUser
- `id` (UUID)
- `email` (String, unique)
- `password_hash` (String)
- `created_at` (Timestamp)

### WaitlistParty
- `id` (UUID)
- `guest_name` (String)
- `phone_number` (String)
- `party_size` (Integer)
- `seating_category` (String)
- `notes` (String, nullable)
- `state` (Enum: `WAITING`, `NOTIFIED`, `SEATED`, `CANCELLED`, `NO_SHOW`, `EXPIRED`)
- `created_at` (Timestamp)
- `notified_at` (Timestamp, nullable)
- `resolved_at` (Timestamp, nullable)

### GuestSession Token
- `id` (UUID)
- `party_id` (FK to WaitlistParty)
- `token_hash` (String)
- `expires_at` (Timestamp)
- `created_at` (Timestamp)

---

## 12. API Surface & WebSockets

### 12.1 REST Endpoints

| Method | Endpoint | Access | Purpose |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/auth/login` | Public | Authenticate Host user |
| `POST` | `/v1/waitlist/join` | Public / Host | Add new party to waitlist |
| `GET` | `/v1/waitlist/active` | Host | Retrieve all active waiting/notified parties |
| `PATCH` | `/v1/waitlist/{id}/state` | Host | Update party state (`NOTIFIED`, `SEATED`, etc.) |
| `POST` | `/v1/waitlist/{id}/push-subscribe` | Guest Token | Register VAPID Web Push subscription |
| `POST` | `/v1/waitlist/{id}/cancel` | Guest Token | Self-cancel spot from guest status page |

### 12.2 WebSocket Events

- **Client -> Server:** `auth_subscribe`, `ping`
- **Server -> Client:** `queue_updated` (broadcast to host), `position_changed` (sent to guest), `table_ready` (sent to guest), `error`

---

## 13. Security, Privacy & Token Lifecycle

- **Guest Token Entropy:** Cryptographically secure 128-bit random bearer tokens.
- **Session Expiry Standards:**
  - Active waiting links: Valid until resolved or max 12-hour hard limit.
  - Resolved links (`SEATED`, `CANCELLED`, `NO_SHOW`): Expire **2 hours** post-resolution.
- **Data Privacy:** Plain-text phone numbers stored during active session; access restricted to authenticated Host endpoints.

---

## 14. Performance, Reliability & Scale Targets

| Metric | Target Specification |
| :--- | :--- |
| **Active Queue Capacity** | 200 concurrent waiting parties per deployment |
| **Host Browsers** | Up to 5 concurrent connected staff sessions |
| **Notification Propagation Latency** | p95 < 1,000 ms (Host action to Guest screen update) |
| **System Availability** | 99.9% uptime during restaurant operational hours |
| **Connection Recovery** | Dynamic WebSocket auto-reconnect within 3 seconds |

---

## 15. Observability & Operational Metrics

- Tracking WebSocket message propagation latency and failure rates.
- Monitoring VAPID Web Push delivery success rates.
- Operational metrics dashboard tracking real-time queue depth and hourly throughput.

---

## 16. MVP Acceptance Criteria

1. Host can log in with email/password and manage active queue entries.
2. Guest can submit public form or be manually entered by Host.
3. Host state changes (`NOTIFIED`, `SEATED`, `CANCELLED`, `NO_SHOW`) update all host devices and target guest device in <1 second (p95).
4. Web Push Notification is triggered on `NOTIFIED` state if permitted; visual banner updates on guest screen regardless of push permissions.
5. Guest can self-cancel from their unique status link.
6. Host can re-notify a notified guest or un-seat a seated guest.
7. Guest status token expires automatically 2 hours after resolution.

---

## 17. Delivery Phases

- **Phase 1 — Core Schema & Host Management:** Auth, Queue CRUD, State Machine, REST APIs.
- **Phase 2 — Real-time Sync & Guest Page:** WebSocket Gateway, Guest Live Status View, Token Expiry.
- **Phase 3 — Web Push & Recovery Controls:** VAPID Integration, Push Fallback Banner, Re-Notify / Un-Seat flows.
- **Phase 4 — Hardening & Production Testing:** Concurrency load testing, WebSocket reconnect resiliency, UI polishing.

---

## 18. Recommended Next Artifacts

1. Clickable UI/UX wireframes for Host Queue Board and Guest Live Status screen.
2. Database migration scripts and VAPID Web Push service worker implementation prototype.