import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { PositionDial } from '../components/PositionDial';
import { StatusBanner } from '../components/StatusBanner';
import { useGuestStatus } from '../hooks/useGuestStatus';

export function GuestStatusPage() {
  const { token = '' } = useParams<{ token: string }>();
  const { status, loading, error, cancel, subscribeToPush } = useGuestStatus(token);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [pushRequested, setPushRequested] = useState(false);

  if (loading) return <p className="help-text guest-page">Loading your status…</p>;

  if (error || !status) {
    return (
      <div className="card guest-page">
        <h1>Link not available</h1>
        <p className="help-text">{error ?? 'This waitlist link could not be found.'}</p>
      </div>
    );
  }

  const canAct = status.state === 'WAITING' || status.state === 'NOTIFIED';

  async function handlePushToggle() {
    setPushRequested(true);
    await subscribeToPush();
  }

  async function handleCancelConfirmed() {
    await cancel();
    setConfirmingCancel(false);
  }

  return (
    <div className="guest-page">
      <h1 style={{ marginBottom: '1rem' }}>{status.guestName}</h1>

      {status.state !== 'WAITING' && <StatusBanner state={status.state} />}

      {status.state === 'WAITING' && status.position !== null && (
        <PositionDial position={status.position} totalWaiting={status.totalWaiting} />
      )}

      <div className="card">
        <p className="help-text" style={{ marginBottom: '1rem' }}>
          Party of {status.partySize} · {status.seatingCategory}
        </p>

        {canAct && (
          <>
            {!status.pushSubscribed && (
              <button type="button" className="btn" onClick={handlePushToggle} disabled={pushRequested} style={{ marginRight: '0.6rem' }}>
                {pushRequested ? 'Notifications on' : 'Get a push alert when ready'}
              </button>
            )}
            {status.pushSubscribed && <p className="help-text" style={{ marginBottom: '0.75rem' }}>Push alerts are on for this device.</p>}

            {!confirmingCancel ? (
              <button type="button" className="btn btn-danger" onClick={() => setConfirmingCancel(true)}>
                Cancel my spot
              </button>
            ) : (
              <div>
                <p style={{ marginBottom: '0.6rem' }}>Cancel your spot in line?</p>
                <button type="button" className="btn btn-danger" onClick={handleCancelConfirmed} style={{ marginRight: '0.5rem' }}>
                  Yes, cancel
                </button>
                <button type="button" className="btn btn-quiet" onClick={() => setConfirmingCancel(false)}>
                  Keep my spot
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
