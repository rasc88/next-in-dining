import type { PartyState } from '../services/types';

const COPY: Partial<Record<PartyState, { title: string; body: string; resolved?: boolean }>> = {
  NOTIFIED: {
    title: 'Your table is ready',
    body: 'Head to the host stand — the team is holding your table.',
  },
  SEATED: {
    title: "You're seated",
    body: 'Enjoy your meal.',
    resolved: true,
  },
  NO_SHOW: {
    title: 'Spot released',
    body: 'This spot was marked as a no-show. Ask the host stand if you have arrived.',
    resolved: true,
  },
  CANCELLED: {
    title: 'Spot cancelled',
    body: 'This spot has been cancelled. Rejoin the waitlist if you would still like a table.',
    resolved: true,
  },
  EXPIRED: {
    title: 'Link expired',
    body: 'This waitlist link is no longer active.',
    resolved: true,
  },
};

export function StatusBanner({ state }: { state: PartyState }) {
  const copy = COPY[state];
  if (!copy) return null;

  return (
    <div className={`status-banner${copy.resolved ? ' resolved' : ''}`} role="status">
      <h2>{copy.title}</h2>
      <p>{copy.body}</p>
    </div>
  );
}
