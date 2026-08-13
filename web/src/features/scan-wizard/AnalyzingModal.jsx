import { useEffect, useState } from 'react';
import {
  ANALYZING_STEP_LABELS,
  formatElapsed,
  getAnalyzingCurrentStepText,
  getAnalyzingSecondaryMessage,
  getAnalyzingStepStatuses,
} from './analyzingProgress.js';

const ICON_BASE = 'flex h-5 w-5 shrink-0 items-center justify-center';

function StepIcon({ status }) {
  if (status === 'done') {
    return (
      <span className={ICON_BASE}>
        <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" className="text-text-secondary">
          <path d="M4 10l4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === 'current') {
    return (
      <span className={ICON_BASE}>
        <span className="h-2.5 w-2.5 rounded-full bg-ink" />
      </span>
    );
  }
  return (
    <span className={ICON_BASE}>
      <span className="h-3 w-3 rounded-full border-2 border-card-border" />
    </span>
  );
}

export default function AnalyzingModal({ open }) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!open) return undefined;
    const startedAt = Date.now();
    setElapsedMs(0);
    const intervalId = setInterval(() => setElapsedMs(Date.now() - startedAt), 250);
    return () => clearInterval(intervalId);
  }, [open]);

  if (!open) return null;

  const statuses = getAnalyzingStepStatuses(elapsedMs);
  const secondaryMessage = getAnalyzingSecondaryMessage(elapsedMs);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="w-full max-w-sm border border-card-border bg-page p-6">
        <div className="flex flex-col items-center text-center">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-card-border border-t-ink" />
          <p className="mt-3 font-heading text-base font-semibold text-ink">{getAnalyzingCurrentStepText(elapsedMs)}</p>
          {secondaryMessage && <p className="mt-1 text-xs text-text-secondary">{secondaryMessage}</p>}
        </div>

        <ol className="mt-5 space-y-2.5">
          {ANALYZING_STEP_LABELS.map((label, index) => (
            <li key={label} className="flex items-center gap-2.5">
              <StepIcon status={statuses[index]} />
              <span
                className={`text-sm ${
                  statuses[index] === 'done'
                    ? 'text-text-secondary line-through'
                    : statuses[index] === 'current'
                      ? 'font-medium text-ink'
                      : 'text-text-secondary'
                }`}
              >
                {label}
              </span>
            </li>
          ))}
        </ol>

        <p className="mt-4 text-center text-xs text-text-secondary">{formatElapsed(elapsedMs)}</p>
      </div>
    </div>
  );
}
