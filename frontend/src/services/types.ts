// Domain types for the Restaurant Waitlist Manager.
// These mirror section 11 (Data Model) and section 7 (Operational State
// Engine) of the spec, so the service layer and UI share one vocabulary
// regardless of which implementation (mock or real HTTP) is behind it.

export type PartyState =
  | 'WAITING'
  | 'NOTIFIED'
  | 'SEATED'
  | 'CANCELLED'
  | 'NO_SHOW'
  | 'EXPIRED';

// The host-triggered actions from the state engine table (section 7).
export type PartyAction = 'NOTIFY' | 'SEAT' | 'NO_SHOW' | 'RE_NOTIFY' | 'UN_SEAT';

export const SEATING_CATEGORIES = ['Indoor', 'Outdoor', 'High-top', 'Bar'] as const;
export type SeatingCategory = (typeof SEATING_CATEGORIES)[number];

export interface WaitlistParty {
  id: string;
  guestName: string;
  phoneNumber: string;
  partySize: number;
  seatingCategory: SeatingCategory | string;
  notes?: string;
  state: PartyState;
  createdAt: string; // ISO timestamp
  notifiedAt?: string;
  resolvedAt?: string;
  pushSubscribed?: boolean;
}

export interface QueueMetrics {
  activeWaiting: number;
  peakHourlyVolume: number;
}

export interface HostUser {
  id: string;
  email: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthSession {
  token: string;
  host: HostUser;
}

export interface JoinWaitlistInput {
  guestName: string;
  phoneNumber: string;
  partySize: number;
  seatingCategory: SeatingCategory | string;
  notes?: string;
}

export interface JoinWaitlistResult {
  party: WaitlistParty;
  guestToken: string;
}

export interface GuestStatus extends WaitlistParty {
  position: number | null; // null once the party is no longer waiting
  totalWaiting: number;
}

export type WaitlistErrorCode =
  | 'INVALID_CREDENTIALS'
  | 'INVALID_TRANSITION'
  | 'NOT_FOUND'
  | 'TOKEN_EXPIRED';

export class WaitlistServiceError extends Error {
  code: WaitlistErrorCode;

  constructor(code: WaitlistErrorCode, message: string) {
    super(message);
    this.name = 'WaitlistServiceError';
    this.code = code;
  }
}
