import type {
  AuthSession,
  GuestStatus,
  JoinWaitlistInput,
  JoinWaitlistResult,
  LoginCredentials,
  PartyAction,
  QueueMetrics,
  WaitlistParty,
} from './types';

/**
 * Every backend interaction the app makes goes through this interface.
 * No component or hook should ever call fetch/WebSocket directly —
 * they depend on IWaitlistService, resolved via ServiceProvider.
 *
 * Method -> spec mapping (section 12):
 *   login              -> POST /v1/auth/login
 *   joinWaitlist       -> POST /v1/waitlist/join
 *   getActiveParties   -> GET  /v1/waitlist/active
 *   updatePartyState   -> PATCH /v1/waitlist/{id}/state
 *   subscribePush      -> POST /v1/waitlist/{id}/push-subscribe
 *   cancelParty        -> POST /v1/waitlist/{id}/cancel
 *   onHostQueueUpdate  -> WS "queue_updated" (server -> host)
 *   onGuestUpdate      -> WS "position_changed" / "table_ready" (server -> guest)
 *
 * Swapping the mock for a real backend means writing one new class that
 * implements this interface (e.g. HttpWaitlistService, wiring the two
 * subscription methods to a real WebSocket) and changing the instance
 * passed to <ServiceProvider>. Nothing else in the app changes.
 */
export interface IWaitlistService {
  login(credentials: LoginCredentials): Promise<AuthSession>;
  logout(): Promise<void>;

  joinWaitlist(input: JoinWaitlistInput): Promise<JoinWaitlistResult>;

  getActiveParties(): Promise<{ parties: WaitlistParty[]; metrics: QueueMetrics }>;

  updatePartyState(partyId: string, action: PartyAction): Promise<WaitlistParty>;

  getGuestStatus(guestToken: string): Promise<GuestStatus>;

  cancelParty(guestToken: string): Promise<WaitlistParty>;

  subscribePush(guestToken: string, subscription: unknown): Promise<void>;

  /** Stands in for the host's WebSocket `queue_updated` channel. Returns an unsubscribe function. */
  onHostQueueUpdate(
    callback: (data: { parties: WaitlistParty[]; metrics: QueueMetrics }) => void,
  ): () => void;

  /** Stands in for the guest's WebSocket `position_changed` / `table_ready` channel. */
  onGuestUpdate(guestToken: string, callback: (status: GuestStatus) => void): () => void;
}
