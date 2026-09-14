import type { QueueMetrics } from '../services/types';

export function MetricsBanner({ metrics }: { metrics: QueueMetrics }) {
  return (
    <div className="metrics-banner" role="group" aria-label="Queue metrics">
      <div>
        <div className="metric-value">{metrics.activeWaiting}</div>
        <div className="metric-label">Parties waiting now</div>
      </div>
      <div>
        <div className="metric-value">{metrics.peakHourlyVolume}</div>
        <div className="metric-label">Peak waiting this shift</div>
      </div>
    </div>
  );
}
