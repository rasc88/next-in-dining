import { useCallback, useEffect, useState } from 'react';
import { useWaitlistService } from '../services';
import type { PartyAction, QueueMetrics, WaitlistParty } from '../services/types';

interface UseHostQueueResult {
  parties: WaitlistParty[];
  metrics: QueueMetrics;
  loading: boolean;
  error: string | null;
  act: (partyId: string, action: PartyAction) => Promise<void>;
}

const EMPTY_METRICS: QueueMetrics = { activeWaiting: 0, peakHourlyVolume: 0 };

export function useHostQueue(): UseHostQueueResult {
  const service = useWaitlistService();
  const [parties, setParties] = useState<WaitlistParty[]>([]);
  const [metrics, setMetrics] = useState<QueueMetrics>(EMPTY_METRICS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    service
      .getActiveParties()
      .then(({ parties: initialParties, metrics: initialMetrics }) => {
        if (cancelled) return;
        setParties(initialParties);
        setMetrics(initialMetrics);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load the queue.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    const unsubscribe = service.onHostQueueUpdate(({ parties: nextParties, metrics: nextMetrics }) => {
      setParties(nextParties);
      setMetrics(nextMetrics);
    });

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, [service]);

  const act = useCallback(
    async (partyId: string, action: PartyAction) => {
      setError(null);
      try {
        await service.updatePartyState(partyId, action);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'That action could not be completed.');
      }
    },
    [service],
  );

  return { parties, metrics, loading, error, act };
}
