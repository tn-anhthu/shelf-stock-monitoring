import { ScanIcon, DashboardIcon, SidebarToggleIcon } from './ui/icons.jsx';
import headerLogo from '../assets/header-logo.svg';

export default function Sidebar({ collapsed, onToggle }) {
  const navItemClass = collapsed
    ? 'flex items-center justify-center rounded-lg py-2.5'
    : 'flex items-center gap-2 rounded-lg px-3 py-2.5';

  return (
    <aside
      className={`hidden shrink-0 flex-col border-r border-card-border bg-white p-4 transition-all duration-200 md:flex ${
        collapsed ? 'w-16' : 'w-56'
      }`}
    >
      <div
        className={
          collapsed
            ? 'mb-6 flex flex-col items-center gap-2'
            : 'mb-6 flex items-center justify-between'
        }
      >
        <img
          src={collapsed ? '/logo.svg' : headerLogo}
          alt="ShelfSense"
          className={collapsed ? 'h-8' : 'h-15'}
        />
        <button
          type="button"
          onClick={onToggle}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-muted hover:bg-page hover:text-ink"
          aria-label={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
          title={collapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
        >
          <SidebarToggleIcon />
        </button>
      </div>
      <nav className="space-y-1">
        <div className={`${navItemClass} bg-ink text-base font-medium text-white`}>
          <ScanIcon />
          {!collapsed && 'Scan'}
        </div>
        <div
          className={`${navItemClass} cursor-not-allowed text-base text-text-muted`}
          title="Sắp có"
        >
          <DashboardIcon />
          {!collapsed && (
            <>
              Dashboard <span className="text-xs">(sắp có)</span>
            </>
          )}
        </div>
      </nav>
    </aside>
  );
}
