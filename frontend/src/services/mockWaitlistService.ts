import type { IWaitlistService } from './IWaitlistService';
import {
  WaitlistServiceError,
  type AuthSession,
  type GuestStatus,
  type HostUser,
  type JoinWaitlistInput,
  type JoinWaitlistResult,
  type LoginCredentials,
  type PartyAction,
  type PartyState,
  type QueueMetrics,
  type WaitlistParty,
} from './types';

// Seeded demo host — printed in the login page's helper text too.
const DEMO_HOST: HostUser = { id: 'host-1', email: 'host@waitlist.test' };
const DEMO_PASSWORD = 'host1234';

// Section 7's state engine, expressed as { state: { action: nextState } }.
const TRANSITIONS: Record<PartyState, Partial<Record<PartyAction, PartyState>>> = {
  WAITING: { NOTIFY: 'NOTIFIED' },
  NOTIFIED: { SEAT: 'SEATED', NO_SHOW: 'NO_SHOW', RE_NOTIFY: 'NOTIFIED' },
  SEATED: { UN_SEAT: 'WAITING' },
  CANCELLED: {},
  NO_SHOW: {},
  EXPIRED: {},
};

function delay(ms = 180): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function randomId(): string {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

type HostListener = (data: { parties: WaitlistParty[]; metrics: QueueMetrics }) => void;
type GuestListener = (status: GuestStatus) => void;

/**
 * A fully in-memory stand-in for the real backend. Holds no external
 * dependencies, so it can back the whole app in development, in tests,
 * or in a demo build with no server running at all.
 */
export class MockWaitlistService implements IWaitlistService {
  private parties: WaitlistParty[] = [];
  private guestTokens = new Map<string, string>(); // token -> partyId
  private peakHourlyVolume = 0;
  private hostListeners = new Set<HostListener>();
  private guestListeners = new Map<string, Set<GuestListener>>();

  constructor(seed = true) {
    if (seed) this.seedDemoData();
  }

  // ---- Auth -------------------------------------------------------------

  async login(credentials: LoginCredentials): Promise<AuthSession> {
    await delay();
    if (credentials.email !== DEMO_HOST.email || credentials.password !== DEMO_PASSWORD) {
      throw new WaitlistServiceError('INVALID_CREDENTIALS', 'Incorrect email or password.');
    }
    return { token: `mock-session-${randomId()}`, host: DEMO_HOST };
  }

  async logout(): Promise<void> {
    await delay(60);
  }

  // ---- Waitlist entry -----------------------------------------------------

  async joinWaitlist(input: JoinWaitlistInput): Promise<JoinWaitlistResult> {
    await delay();
    const party: WaitlistParty = {
      id: randomId(),
      guestName: input.guestName,
      phoneNumber: input.phoneNumber,
      partySize: input.partySize,
      seatingCategory: input.seatingCategory,
      notes: input.notes,
      state: 'WAITING',
      createdAt: new Date().toISOString(),
    };
    this.parties.push(party);

    const guestToken = `guest-${randomId()}`;
    this.guestTokens.set(guestToken, party.id);

    this.recomputePeak();
    this.notifyHostListeners();
    return { party, guestToken };
  }

  async getActiveParties(): Promise<{ parties: WaitlistParty[]; metrics: QueueMetrics }> {
    await delay();
    return { parties: this.visibleParties(), metrics: this.currentMetrics() };
  }

  async updatePartyState(partyId: string, action: PartyAction): Promise<WaitlistParty> {
    await delay();
    const party = this.parties.find((p) => p.id === partyId);
    if (!party) throw new WaitlistServiceError('NOT_FOUND', `No party with id ${partyId}.`);

    const nextState = TRANSITIONS[party.state][action];
    if (!nextState) {
      throw new WaitlistServiceError(
        'INVALID_TRANSITION',
        `Cannot apply "${action}" to a party in state "${party.state}".`,
      );
    }

    party.state = nextState;
    if (action === 'NOTIFY' || action === 'RE_NOTIFY') party.notifiedAt = new Date().toISOString();
    if (action === 'SEAT' || action === 'NO_SHOW') party.resolvedAt = new Date().toISOString();
    if (action === 'UN_SEAT') party.resolvedAt = undefined;

    this.recomputePeak();
    this.notifyHostListeners();
    this.notifyGuestListenersForParty(party.id);
    return party;
  }

  // ---- Guest status ---------------------------------------------------

  async getGuestStatus(guestToken: string): Promise<GuestStatus> {
    await delay();
    return this.buildGuestStatus(guestToken);
  }

  async cancelParty(guestToken: string): Promise<WaitlistParty> {
    await delay();
    const party = this.resolvePartyByToken(guestToken);
    if (party.state !== 'WAITING' && party.state !== 'NOTIFIED') {
      throw new WaitlistServiceError(
        'INVALID_TRANSITION',
        `A party in state "${party.state}" can no longer be cancelled.`,
      );
    }
    party.state = 'CANCELLED';
    party.resolvedAt = new Date().toISOString();

    this.notifyHostListeners();
    this.notifyGuestListenersForParty(party.id);
    return party;
  }

  async subscribePush(guestToken: string, _subscription: unknown): Promise<void> {
    await delay(80);
    const party = this.resolvePartyByToken(guestToken);
    party.pushSubscribed = true;
    this.notifyGuestListenersForParty(party.id);
  }

  // ---- Realtime (WebSocket stand-ins) ----------------------------------

  onHostQueueUpdate(callback: HostListener): () => void {
    this.hostListeners.add(callback);
    return () => this.hostListeners.delete(callback);
  }

  onGuestUpdate(guestToken: string, callback: GuestListener): () => void {
    if (!this.guestListeners.has(guestToken)) this.guestListeners.set(guestToken, new Set());
    const set = this.guestListeners.get(guestToken)!;
    set.add(callback);
    return () => set.delete(callback);
  }

  // ---- Internal helpers -------------------------------------------------

  private resolvePartyByToken(guestToken: string): WaitlistParty {
    const partyId = this.guestTokens.get(guestToken);
    const party = partyId ? this.parties.find((p) => p.id === partyId) : undefined;
    if (!party) throw new WaitlistServiceError('TOKEN_EXPIRED', 'This guest link is no longer valid.');
    return party;
  }

  private buildGuestStatus(guestToken: string): GuestStatus {
    const party = this.resolvePartyByToken(guestToken);
    const waitingInOrder = this.parties
      .filter((p) => p.state === 'WAITING')
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    const position = party.state === 'WAITING' ? waitingInOrder.findIndex((p) => p.id === party.id) + 1 : null;
    return { ...party, position, totalWaiting: waitingInOrder.length };
  }

  private visibleParties(): WaitlistParty[] {
    // The host board (spec 6.2) shows everything still relevant to the
    // shift: active parties plus recently resolved ones for recovery
    // actions (re-notify / un-seat), oldest first.
    return [...this.parties].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  private currentMetrics(): QueueMetrics {
    return {
      activeWaiting: this.parties.filter((p) => p.state === 'WAITING').length,
      peakHourlyVolume: this.peakHourlyVolume,
    };
  }

  private recomputePeak(): void {
    const waiting = this.parties.filter((p) => p.state === 'WAITING').length;
    this.peakHourlyVolume = Math.max(this.peakHourlyVolume, waiting);
  }

  private notifyHostListeners(): void {
    const snapshot = { parties: this.visibleParties(), metrics: this.currentMetrics() };
    this.hostListeners.forEach((listener) => listener(snapshot));
  }

  private notifyGuestListenersForParty(partyId: string): void {
    for (const [token, partyIdForToken] of this.guestTokens.entries()) {
      if (partyIdForToken !== partyId) continue;
      const listeners = this.guestListeners.get(token);
      if (listeners?.size) listeners.forEach((listener) => listener(this.buildGuestStatus(token)));
    }
  }

  private seedDemoData(): void {
    const now = Date.now();
    const minutesAgo = (m: number) => new Date(now - m * 60_000).toISOString();
    this.parties = [
      {
        id: 'seed-1',
        guestName: 'Marta Vidal',
        phoneNumber: '507-6000-1111',
        partySize: 2,
        seatingCategory: 'Indoor',
        state: 'WAITING',
        createdAt: minutesAgo(18),
      },
      {
        id: 'seed-2',
        guestName: 'Chen Family',
        phoneNumber: '507-6000-2222',
        partySize: 4,
        seatingCategory: 'Outdoor',
        state: 'WAITING',
        createdAt: minutesAgo(11),
      },
      {
        id: 'seed-3',
        guestName: 'Isabel Ríos',
        phoneNumber: '507-6000-3333',
        partySize: 1,
        seatingCategory: 'Bar',
        state: 'NOTIFIED',
        createdAt: minutesAgo(24),
        notifiedAt: minutesAgo(2),
      },
    ];
    this.guestTokens.set('demo-guest-token', 'seed-1');
    this.recomputePeak();
  }
}

/** Shared instance used by the running app (see ServiceProvider's default). */
export const mockWaitlistService = new MockWaitlistService();
