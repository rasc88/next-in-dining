import type { IWaitlistService } from './IWaitlistService';
import {
  WaitlistServiceError,
  type AuthSession,
  type GuestStatus,
  type JoinWaitlistInput,
  type JoinWaitlistResult,
  type LoginCredentials,
  type PartyAction,
  type QueueMetrics,
  type WaitlistErrorCode,
  type WaitlistParty,
} from './types';

const DEFAULT_BASE_URL = 'http://localhost:8000/v1';
const POLL_INTERVAL_MS = 3000;

interface ApiErrorBody {
  code: WaitlistErrorCode;
  message: string;
}

function isApiErrorBody(data: unknown): data is ApiErrorBody {
  return (
    typeof data === 'object' &&
    data !== null &&
    typeof (data as ApiErrorBody).code === 'string' &&
    typeof (data as ApiErrorBody).message === 'string'
  );
}

async function apiRequest<T>(
  baseUrl: string,
  path: string,
  options: { method?: string; token?: string; body?: unknown } = {},
): Promise<T> {
  const { method = 'GET', token, body } = options;
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) return undefined as T;

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (isApiErrorBody(data)) throw new WaitlistServiceError(data.code, data.message);
    throw new Error(`Request failed with status ${response.status}.`);
  }

  return data as T;
}

/**
 * Talks to the real FastAPI backend (backend/) over REST. That backend has
 * no WebSocket gateway yet, so the two realtime methods poll their
 * matching GET endpoint instead of holding an open socket — every other
 * method maps one call to one request per IWaitlistService's doc comment.
 */
export class RestWaitlistService implements IWaitlistService {
  private hostToken: string | null = null;
  private readonly baseUrl: string;
  private readonly pollIntervalMs: number;

  constructor(baseUrl: string = DEFAULT_BASE_URL, pollIntervalMs: number = POLL_INTERVAL_MS) {
    this.baseUrl = baseUrl;
    this.pollIntervalMs = pollIntervalMs;
  }

  async login(credentials: LoginCredentials): Promise<AuthSession> {
    const session = await apiRequest<AuthSession>(this.baseUrl, '/auth/login', {
      method: 'POST',
      body: credentials,
    });
    this.hostToken = session.token;
    return session;
  }

  async logout(): Promise<void> {
    const token = this.hostToken;
    this.hostToken = null;
    if (!token) return;
    await apiRequest<void>(this.baseUrl, '/auth/logout', { method: 'POST', token });
  }

  async joinWaitlist(input: JoinWaitlistInput): Promise<JoinWaitlistResult> {
    return apiRequest<JoinWaitlistResult>(this.baseUrl, '/waitlist/join', {
      method: 'POST',
      body: input,
    });
  }

  async getActiveParties(): Promise<{ parties: WaitlistParty[]; metrics: QueueMetrics }> {
    return apiRequest(this.baseUrl, '/waitlist/active', { token: this.requireHostToken() });
  }

  async updatePartyState(partyId: string, action: PartyAction): Promise<WaitlistParty> {
    return apiRequest<WaitlistParty>(this.baseUrl, `/waitlist/${partyId}/state`, {
      method: 'PATCH',
      token: this.requireHostToken(),
      body: { action },
    });
  }

  async getGuestStatus(guestToken: string): Promise<GuestStatus> {
    return apiRequest<GuestStatus>(this.baseUrl, '/waitlist/me', { token: guestToken });
  }

  async cancelParty(guestToken: string): Promise<WaitlistParty> {
    return apiRequest<WaitlistParty>(this.baseUrl, '/waitlist/me/cancel', {
      method: 'POST',
      token: guestToken,
    });
  }

  async subscribePush(guestToken: string, subscription: unknown): Promise<void> {
    await apiRequest<void>(this.baseUrl, '/waitlist/me/push-subscribe', {
      method: 'POST',
      token: guestToken,
      body: subscription,
    });
  }

  onHostQueueUpdate(
    callback: (data: { parties: WaitlistParty[]; metrics: QueueMetrics }) => void,
  ): () => void {
    const interval = setInterval(() => {
      this.getActiveParties()
        .then(callback)
        .catch((err) => console.error('Failed to poll the active queue.', err));
    }, this.pollIntervalMs);
    return () => clearInterval(interval);
  }

  onGuestUpdate(guestToken: string, callback: (status: GuestStatus) => void): () => void {
    const interval = setInterval(() => {
      this.getGuestStatus(guestToken)
        .then(callback)
        .catch((err) => console.error('Failed to poll guest status.', err));
    }, this.pollIntervalMs);
    return () => clearInterval(interval);
  }

  private requireHostToken(): string {
    if (!this.hostToken) throw new WaitlistServiceError('TOKEN_EXPIRED', 'Not signed in.');
    return this.hostToken;
  }
}

/** Shared instance used by the running app (see ServiceProvider's default). */
export const restWaitlistService = new RestWaitlistService(
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_BASE_URL,
);
