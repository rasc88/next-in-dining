import type { PartyAction, WaitlistParty } from '../services/types';

const STATE_LABELS: Record<WaitlistParty['state'], string> = {
  WAITING: 'Waiting',
  NOTIFIED: 'Notified',
  SEATED: 'Seated',
  CANCELLED: 'Cancelled',
  NO_SHOW: 'No-show',
  EXPIRED: 'Expired',
};

function minutesSince(iso: string): number {
  return Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000));
}

export function QueueRow({
  party,
  onAction,
}: {
  party: WaitlistParty;
  onAction: (partyId: string, action: PartyAction) => void;
}) {
  const waited = minutesSince(party.createdAt);

  return (
    <div className="ledger-row">
      <div className="party-details">
        <div className="party-name">
          {party.guestName} · party of {party.partySize}
        </div>
        <div className="party-meta">
          {party.seatingCategory} · waiting {waited} min
        </div>
      </div>

      <span className={`state-pill state-${party.state}`}>{STATE_LABELS[party.state]}</span>

      <div className="actions">
        {party.state === 'WAITING' && (
          <button type="button" className="btn btn-ready" onClick={() => onAction(party.id, 'NOTIFY')}>
            Notify
          </button>
        )}
        {party.state === 'NOTIFIED' && (
          <>
            <button type="button" className="btn btn-primary" onClick={() => onAction(party.id, 'SEAT')}>
              Seat
            </button>
            <button type="button" className="btn btn-danger" onClick={() => onAction(party.id, 'NO_SHOW')}>
              No-show
            </button>
            <button type="button" className="btn btn-quiet" onClick={() => onAction(party.id, 'RE_NOTIFY')}>
              Re-notify
            </button>
          </>
        )}
        {party.state === 'SEATED' && (
          <button type="button" className="btn btn-quiet" onClick={() => onAction(party.id, 'UN_SEAT')}>
            Un-seat
          </button>
        )}
      </div>
    </div>
  );
}
