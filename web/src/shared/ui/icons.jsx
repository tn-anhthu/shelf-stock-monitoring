export function ScanIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
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
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <rect x="4" y="12" width="4" height="8" />
      <rect x="10" y="8" width="4" height="12" />
      <rect x="16" y="4" width="4" height="16" />
    </svg>
  );
}

export function SidebarToggleIcon(props) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <line x1="9" y1="4" x2="9" y2="20" />
    </svg>
  );
}

export function IconCheck({ className = '' }) {
  return (
    <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <path d="M4 10l4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconClose({ className = '' }) {
  return (
    <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" className={className}>
      <path d="M5 5l10 10M15 5L5 15" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconLock({ className = '' }) {
  return (
    <svg viewBox="0 0 20 20" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.6" className={className}>
      <rect x="4.5" y="9" width="11" height="8" rx="1.5" />
      <path d="M6.5 9V6.5a3.5 3.5 0 0 1 7 0V9" strokeLinecap="round" />
    </svg>
  );
}
