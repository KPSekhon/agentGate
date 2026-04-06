interface AnomalyBadgeProps {
  score: number;
}

export default function AnomalyBadge({ score }: AnomalyBadgeProps) {
  if (score <= 0.3) {
    return (
      <span className="px-2 py-0.5 text-xs rounded bg-green-900/40 text-green-400">
        {score.toFixed(1)}
      </span>
    );
  }
  if (score <= 0.5) {
    return (
      <span className="px-2 py-0.5 text-xs rounded bg-yellow-900/40 text-yellow-400">
        {score.toFixed(1)}
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 text-xs rounded bg-red-900/40 text-red-400 font-semibold animate-pulse">
      {score.toFixed(1)}
    </span>
  );
}
