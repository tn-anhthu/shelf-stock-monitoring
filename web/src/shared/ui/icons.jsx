export function ScanIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <path d="M4 8V6a2 2 0 0 1 2-2h2" strokeLinecap="round" />
      <path d="M16 4h2a2 2 0 0 1 2 2v2" strokeLinecap="round" />
      <path d="M20 16v2a2 2 0 0 1-2 2h-2" strokeLinecap="round" />
      <path d="M8 20H6a2 2 0 0 1-2-2v-2" strokeLinecap="round" />
      <rect x="7" y="7" width="10" height="10" rx="1" />
    </svg>
  );
}

export function DashboardIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <rect x="4" y="12" width="4" height="8" />
      <rect x="10" y="8" width="4" height="12" />
      <rect x="16" y="4" width="4" height="16" />
    </svg>
  );
}
