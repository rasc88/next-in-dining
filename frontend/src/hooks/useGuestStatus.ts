import { useCallback, useEffect, useState } from 'react';
import { useWaitlistService } from '../services';
import type { GuestStatus } from '../services/types';

interface UseGuestStatusResult {
  status: GuestStatus | null;
  loading: boolean;
  error: string | null;
  cancel: () => Promise<void>;
  subscribeToPush: () => Promise<void>;
}

export function useGuestStatus(guestToken: string): UseGuestStatusResult {
  const service = useWaitlistService();
  const [status, setStatus] = useState<GuestStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    service
      .getGuestStatus(guestToken)
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'This link is no longer valid.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const unsubscribe = service.onGuestUpdate(guestToken, (nextStatus) => {
      setStatus(nextStatus);
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [service, guestToken]);

  const cancel = useCallback(async () => {
    setError(null);
    try {
      await service.cancelParty(guestToken);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not cancel this spot.');
    }
  }, [service, guestToken]);

  const subscribeToPush = useCallback(async () => {
    // A real implementation would request Notification permission and
    // register a PushSubscription here before handing it to the service.
    await service.subscribePush(guestToken, { mock: true });
  }, [service, guestToken]);

  return { status, loading, error, cancel, subscribeToPush };
}
