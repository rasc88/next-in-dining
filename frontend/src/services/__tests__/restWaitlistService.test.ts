import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RestWaitlistService } from '../restWaitlistService';
import { WaitlistServiceError } from '../types';

const BASE_URL = 'http://api.test/v1';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function noContentResponse(): Response {
  return new Response(null, { status: 204 });
}

describe('RestWaitlistService', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let service: RestWaitlistService;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    service = new RestWaitlistService(BASE_URL);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('login', () => {
    it('posts credentials and resolves the session', async () => {
      const session = { token: 'host-token-123', host: { id: 'h1', email: 'host@waitlist.test' } };
      fetchMock.mockResolvedValueOnce(jsonResponse(session));

      const result = await service.login({ email: 'host@waitlist.test', password: 'host1234' });

      expect(result).toEqual(session);
      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toBe(`${BASE_URL}/auth/login`);
      expect(init.method).toBe('POST');
      expect(JSON.parse(init.body)).toEqual({ email: 'host@waitlist.test', password: 'host1234' });
    });

    it('rejects with a WaitlistServiceError on invalid credentials', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ code: 'INVALID_CREDENTIALS', message: 'Incorrect email or password.' }, 401),
      );

      await expect(service.login({ email: 'host@waitlist.test', password: 'wrong' })).rejects.toMatchObject({
        code: 'INVALID_CREDENTIALS',
      });
    });
  });

  describe('host-authenticated calls', () => {
    it('attaches the bearer token obtained from login', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ token: 'host-token-123', host: { id: 'h1', email: 'host@waitlist.test' } }),
      );
      await service.login({ email: 'host@waitlist.test', password: 'host1234' });

      fetchMock.mockResolvedValueOnce(
        jsonResponse({ parties: [], metrics: { activeWaiting: 0, peakHourlyVolume: 0 } }),
      );
      await service.getActiveParties();

      const [, init] = fetchMock.mock.calls[1];
      expect(init.headers.Authorization).toBe('Bearer host-token-123');
    });

    it('rejects host calls made before logging in', async () => {
      await expect(service.getActiveParties()).rejects.toMatchObject({ code: 'TOKEN_EXPIRED' });
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('sends the action body on a state transition', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ token: 'host-token-123', host: { id: 'h1', email: 'host@waitlist.test' } }),
      );
      await service.login({ email: 'host@waitlist.test', password: 'host1234' });

      fetchMock.mockResolvedValueOnce(jsonResponse({ id: 'p1', state: 'NOTIFIED' }));
      await service.updatePartyState('p1', 'NOTIFY');

      const [url, init] = fetchMock.mock.calls[1];
      expect(url).toBe(`${BASE_URL}/waitlist/p1/state`);
      expect(init.method).toBe('PATCH');
      expect(JSON.parse(init.body)).toEqual({ action: 'NOTIFY' });
    });

    it('clears the stored token on logout, even before the request resolves', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ token: 'host-token-123', host: { id: 'h1', email: 'host@waitlist.test' } }),
      );
      await service.login({ email: 'host@waitlist.test', password: 'host1234' });

      fetchMock.mockResolvedValueOnce(noContentResponse());
      await service.logout();

      await expect(service.getActiveParties()).rejects.toMatchObject({ code: 'TOKEN_EXPIRED' });
    });
  });

  describe('guest-token calls', () => {
    it('passes the guest token explicitly, independent of any host session', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ id: 'p1', state: 'WAITING', position: 1, totalWaiting: 1 }),
      );

      const status = await service.getGuestStatus('guest-token-abc');

      expect(status.position).toBe(1);
      const [url, init] = fetchMock.mock.calls[0];
      expect(url).toBe(`${BASE_URL}/waitlist/me`);
      expect(init.headers.Authorization).toBe('Bearer guest-token-abc');
    });

    it('surfaces INVALID_TRANSITION when cancelling a resolved party', async () => {
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ code: 'INVALID_TRANSITION', message: 'A party in state "SEATED" can no longer be cancelled.' }, 409),
      );

      await expect(service.cancelParty('guest-token-abc')).rejects.toBeInstanceOf(WaitlistServiceError);
    });

    it('posts the subscription payload as the request body', async () => {
      fetchMock.mockResolvedValueOnce(noContentResponse());
      const subscription = { endpoint: 'https://push.example/x', keys: { p256dh: 'a', auth: 'b' } };

      await service.subscribePush('guest-token-abc', subscription);

      const [, init] = fetchMock.mock.calls[0];
      expect(JSON.parse(init.body)).toEqual(subscription);
    });
  });

  describe('error handling', () => {
    it('throws a plain Error when the server response has no recognizable error body', async () => {
      fetchMock.mockResolvedValueOnce(new Response('Internal Server Error', { status: 500 }));

      await expect(service.joinWaitlist({
        guestName: 'A',
        phoneNumber: '1',
        partySize: 1,
        seatingCategory: 'Indoor',
      })).rejects.toThrow('Request failed with status 500.');
    });
  });

  describe('realtime polling stand-ins', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('polls getActiveParties on an interval and stops after unsubscribing', async () => {
      service = new RestWaitlistService(BASE_URL, 1000);
      fetchMock.mockResolvedValueOnce(
        jsonResponse({ token: 'host-token-123', host: { id: 'h1', email: 'host@waitlist.test' } }),
      );
      await service.login({ email: 'host@waitlist.test', password: 'host1234' });

      const listener = vi.fn();
      const unsubscribe = service.onHostQueueUpdate(listener);

      fetchMock.mockResolvedValueOnce(
        jsonResponse({ parties: [], metrics: { activeWaiting: 0, peakHourlyVolume: 0 } }),
      );
      await vi.advanceTimersByTimeAsync(1000);
      expect(listener).toHaveBeenCalledTimes(1);

      unsubscribe();
      await vi.advanceTimersByTimeAsync(2000);
      expect(listener).toHaveBeenCalledTimes(1);
    });
  });
});
