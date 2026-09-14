import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MockWaitlistService } from '../mockWaitlistService';
import { WaitlistServiceError } from '../types';

describe('MockWaitlistService', () => {
  let service: MockWaitlistService;

  beforeEach(() => {
    // Fresh, unseeded instance per test for isolated, predictable state.
    service = new MockWaitlistService(false);
  });

  describe('login', () => {
    it('resolves a session for the seeded demo host', async () => {
      const session = await service.login({ email: 'host@waitlist.test', password: 'host1234' });
      expect(session.host.email).toBe('host@waitlist.test');
      expect(session.token).toMatch(/^mock-session-/);
    });

    it('rejects incorrect credentials', async () => {
      await expect(service.login({ email: 'host@waitlist.test', password: 'wrong' })).rejects.toMatchObject({
        code: 'INVALID_CREDENTIALS',
      });
    });
  });

  describe('joinWaitlist', () => {
    it('creates a WAITING party and returns a guest token that resolves status', async () => {
      const { party, guestToken } = await service.joinWaitlist({
        guestName: 'Ada Lovelace',
        phoneNumber: '555-0100',
        partySize: 3,
        seatingCategory: 'Indoor',
      });

      expect(party.state).toBe('WAITING');
      expect(guestToken).toMatch(/^guest-/);

      const { parties } = await service.getActiveParties();
      expect(parties).toHaveLength(1);
      expect(parties[0].id).toBe(party.id);

      const status = await service.getGuestStatus(guestToken);
      expect(status.position).toBe(1);
      expect(status.totalWaiting).toBe(1);
    });

    it('computes position relative to other waiting parties, oldest first', async () => {
      const first = await service.joinWaitlist({
        guestName: 'First',
        phoneNumber: '1',
        partySize: 2,
        seatingCategory: 'Indoor',
      });
      const second = await service.joinWaitlist({
        guestName: 'Second',
        phoneNumber: '2',
        partySize: 2,
        seatingCategory: 'Indoor',
      });

      const firstStatus = await service.getGuestStatus(first.guestToken);
      const secondStatus = await service.getGuestStatus(second.guestToken);
      expect(firstStatus.position).toBe(1);
      expect(secondStatus.position).toBe(2);
    });
  });

  describe('updatePartyState (the section 7 state engine)', () => {
    it('moves WAITING -> NOTIFIED via NOTIFY and stamps notifiedAt', async () => {
      const { party } = await service.joinWaitlist({
        guestName: 'Grace Hopper',
        phoneNumber: '555-0101',
        partySize: 2,
        seatingCategory: 'Bar',
      });

      const updated = await service.updatePartyState(party.id, 'NOTIFY');
      expect(updated.state).toBe('NOTIFIED');
      expect(updated.notifiedAt).toBeDefined();
    });

    it('moves NOTIFIED -> SEATED via SEAT and stamps resolvedAt', async () => {
      const { party } = await service.joinWaitlist({
        guestName: 'Alan Turing',
        phoneNumber: '555-0102',
        partySize: 1,
        seatingCategory: 'Outdoor',
      });
      await service.updatePartyState(party.id, 'NOTIFY');

      const seated = await service.updatePartyState(party.id, 'SEAT');
      expect(seated.state).toBe('SEATED');
      expect(seated.resolvedAt).toBeDefined();
    });

    it('allows SEATED -> WAITING via UN_SEAT (recovery action)', async () => {
      const { party } = await service.joinWaitlist({
        guestName: 'Margaret Hamilton',
        phoneNumber: '555-0103',
        partySize: 4,
        seatingCategory: 'High-top',
      });
      await service.updatePartyState(party.id, 'NOTIFY');
      await service.updatePartyState(party.id, 'SEAT');

      const backToWaiting = await service.updatePartyState(party.id, 'UN_SEAT');
      expect(backToWaiting.state).toBe('WAITING');
    });

    it('rejects an action that is not valid for the current state', async () => {
      const { party } = await service.joinWaitlist({
        guestName: 'Katherine Johnson',
        phoneNumber: '555-0104',
        partySize: 2,
        seatingCategory: 'Indoor',
      });

      // Cannot SEAT a party that hasn't been NOTIFIED yet.
      await expect(service.updatePartyState(party.id, 'SEAT')).rejects.toMatchObject({
        code: 'INVALID_TRANSITION',
      });
    });

    it('throws NOT_FOUND for an unknown party id', async () => {
      await expect(service.updatePartyState('missing-id', 'NOTIFY')).rejects.toBeInstanceOf(
        WaitlistServiceError,
      );
    });
  });

  describe('cancelParty', () => {
    it('lets a guest cancel from WAITING', async () => {
      const { guestToken } = await service.joinWaitlist({
        guestName: 'Radia Perlman',
        phoneNumber: '555-0105',
        partySize: 2,
        seatingCategory: 'Indoor',
      });

      const cancelled = await service.cancelParty(guestToken);
      expect(cancelled.state).toBe('CANCELLED');
    });

    it('rejects cancelling an already-seated party', async () => {
      const { party, guestToken } = await service.joinWaitlist({
        guestName: 'Hedy Lamarr',
        phoneNumber: '555-0106',
        partySize: 2,
        seatingCategory: 'Indoor',
      });
      await service.updatePartyState(party.id, 'NOTIFY');
      await service.updatePartyState(party.id, 'SEAT');

      await expect(service.cancelParty(guestToken)).rejects.toMatchObject({ code: 'INVALID_TRANSITION' });
    });
  });

  describe('realtime subscriptions (WebSocket stand-ins)', () => {
    it('notifies host listeners whenever the queue changes', async () => {
      const listener = vi.fn();
      const unsubscribe = service.onHostQueueUpdate(listener);

      await service.joinWaitlist({
        guestName: 'Joan Clarke',
        phoneNumber: '555-0107',
        partySize: 2,
        seatingCategory: 'Indoor',
      });

      expect(listener).toHaveBeenCalledTimes(1);
      const [snapshot] = listener.mock.calls[0];
      expect(snapshot.metrics.activeWaiting).toBe(1);

      unsubscribe();
      await service.joinWaitlist({
        guestName: 'Dorothy Vaughan',
        phoneNumber: '555-0108',
        partySize: 2,
        seatingCategory: 'Indoor',
      });
      expect(listener).toHaveBeenCalledTimes(1); // no further calls after unsubscribe
    });

    it('notifies only the matching guest listener on that party\'s changes', async () => {
      const { party, guestToken } = await service.joinWaitlist({
        guestName: 'Mary Jackson',
        phoneNumber: '555-0109',
        partySize: 2,
        seatingCategory: 'Indoor',
      });
      const guestListener = vi.fn();
      service.onGuestUpdate(guestToken, guestListener);

      await service.updatePartyState(party.id, 'NOTIFY');

      expect(guestListener).toHaveBeenCalledTimes(1);
      expect(guestListener.mock.calls[0][0].state).toBe('NOTIFIED');
    });
  });
});
