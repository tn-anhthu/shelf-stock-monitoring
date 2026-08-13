import { ScanIcon, DashboardIcon, SidebarToggleIcon } from './ui/icons.jsx';
import headerLogo from '../assets/header-logo.svg';

const NAV_ITEMS = [
  { id: 'scan', label: 'Scan', Icon: ScanIcon },
  { id: 'inventory', label: 'Inventory', Icon: DashboardIcon },
];

export default function Sidebar({ collapsed, onToggle, activeTab, onSelectTab }) {
  const navItemClass = collapsed
    ? 'flex w-full items-center justify-center rounded-lg py-2.5'
    : 'flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left';

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
        {NAV_ITEMS.map(({ id, label, Icon }) => {
          const isActive = activeTab === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelectTab(id)}
              className={`${navItemClass} text-base ${
                isActive ? 'bg-ink font-medium text-white' : 'text-text-secondary hover:bg-page hover:text-ink'
              }`}
            >
              <Icon />
              {!collapsed && label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
