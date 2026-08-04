import { ScanIcon, DashboardIcon } from './ui/icons.jsx';

export default function BottomNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 flex border-t border-card-border bg-white md:hidden">
      <div className="flex flex-1 flex-col items-center gap-0.5 py-2 text-ink">
        <ScanIcon />
        <span className="text-xs font-medium">Scan</span>
      </div>
      <div
        className="flex flex-1 flex-col items-center gap-0.5 py-2 text-text-muted"
        title="Sắp có"
      >
        <DashboardIcon />
        <span className="text-xs">Dashboard</span>
      </div>
    </nav>
  );
}
