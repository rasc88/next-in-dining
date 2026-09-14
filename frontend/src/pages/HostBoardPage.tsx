import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { CategoryTabs } from '../components/CategoryTabs';
import { MetricsBanner } from '../components/MetricsBanner';
import { QueueRow } from '../components/QueueRow';
import { useHostQueue } from '../hooks/useHostQueue';

export function HostBoardPage() {
  const { parties, metrics, loading, error, act } = useHostQueue();
  const [activeCategory, setActiveCategory] = useState('All');

  const categories = useMemo(
    () => Array.from(new Set(parties.map((p) => p.seatingCategory))).sort(),
    [parties],
  );

  const visibleParties = useMemo(
    () => parties.filter((p) => activeCategory === 'All' || p.seatingCategory === activeCategory),
    [parties, activeCategory],
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '1rem' }}>
        <h1>Tonight&apos;s queue</h1>
        <Link to="/join" className="help-text">
          Guest check-in link ↗
        </Link>
      </div>

      <MetricsBanner metrics={metrics} />

      <CategoryTabs categories={categories} active={activeCategory} onSelect={setActiveCategory} />

      {error && (
        <p className="error-text" role="alert">
          {error}
        </p>
      )}

      {loading ? (
        <p className="help-text">Loading the queue…</p>
      ) : visibleParties.length === 0 ? (
        <div className="empty-state">No parties in this category right now.</div>
      ) : (
        <div className="ledger">
          {visibleParties.map((party) => (
            <QueueRow key={party.id} party={party} onAction={act} />
          ))}
        </div>
      )}
    </div>
  );
}
