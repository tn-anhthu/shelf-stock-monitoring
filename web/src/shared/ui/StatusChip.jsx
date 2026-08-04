import { getStatusStyle } from './statusStyles.js';

export default function StatusChip({ status }) {
  const style = getStatusStyle(status);
  if (!style) {
    return <span className="text-text-muted">—</span>;
  }
  return (
    <span
      className="rounded-md px-2 py-0.5 text-xs font-medium"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {style.label}
    </span>
  );
}
