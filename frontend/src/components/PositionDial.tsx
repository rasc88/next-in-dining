export function PositionDial({ position, totalWaiting }: { position: number; totalWaiting: number }) {
  const aheadCount = Math.max(0, position - 1);

  return (
    <div className="position-hero">
      <div className="position-number">{position}</div>
      <div className="position-label">
        {aheadCount === 0
          ? "You're next in line"
          : `${aheadCount} ${aheadCount === 1 ? 'party is' : 'parties are'} ahead of you`}
      </div>
      <p className="help-text" style={{ marginTop: '0.75rem' }}>
        {totalWaiting} {totalWaiting === 1 ? 'party' : 'parties'} waiting in total
      </p>
    </div>
  );
}
