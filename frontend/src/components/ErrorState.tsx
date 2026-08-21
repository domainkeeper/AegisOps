interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="error-state">
      <strong>Error:</strong> {message}
      {onRetry && <button className="btn" onClick={onRetry} style={{ marginLeft: '0.75rem' }}>Retry</button>}
    </div>
  );
}