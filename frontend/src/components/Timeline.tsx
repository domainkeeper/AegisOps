import type { TimelineEvent } from '../types/api';
import { StatusBadge } from './StatusBadge';

interface TimelineProps {
  events: TimelineEvent[];
}

function formatTs(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function Timeline({ events }: TimelineProps) {
  if (!events.length) return <div className="empty-state"><div className="empty-state-icon">◻</div>No timeline events</div>;
  
  return (
    <ul className="timeline">
      {events.map((e, i) => (
        <li key={i} className={`timeline-item ${e.status.toLowerCase()}`}>
          <span className="timeline-time">{formatTs(e.ts)}</span>
          <div className="timeline-content">
            <div className="timeline-stage">
              {e.stage.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
              <StatusBadge status={e.status} label="" />
            </div>
            {e.detail && <div className="timeline-detail">{e.detail}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}