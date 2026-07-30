import { ScanIcon, DashboardIcon } from './ui/icons.jsx';

export default function Sidebar() {
  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-card-border bg-white p-4 md:flex">
      <h1 className="mb-6 font-heading text-lg font-semibold text-ink">ShelfSense</h1>
      <nav className="space-y-1">
        <div className="flex items-center gap-2 rounded-lg bg-ink px-3 py-2 text-sm font-medium text-white">
          <ScanIcon />
          Scan
        </div>
        <div
          className="flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm text-text-muted"
          title="Sắp có"
        >
          <DashboardIcon />
          Dashboard <span className="text-xs">(sắp có)</span>
        </div>
      </nav>
    </aside>
  );
}
