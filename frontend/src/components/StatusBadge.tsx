interface StatusBadgeProps {
  status: string;
  label?: string;
  dot?: boolean;
}

export function StatusBadge({ status, label, dot }: StatusBadgeProps) {
  const safeStatus = status || 'unknown';
  const cls = safeStatus.toLowerCase().replace(/\s+/g, '_');
  return (
    <span className={`status-badge ${cls}`}>
      {dot && <span className={`status-dot ${cls}`} />}
      {label || safeStatus}
    </span>
  );
}
