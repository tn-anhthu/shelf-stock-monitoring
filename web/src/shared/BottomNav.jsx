import { ScanIcon, DashboardIcon } from './ui/icons.jsx';

const NAV_ITEMS = [
  { id: 'scan', label: 'Scan', Icon: ScanIcon },
  { id: 'inventory', label: 'Inventory', Icon: DashboardIcon },
];

export default function BottomNav({ activeTab, onSelectTab }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 flex border-t border-card-border bg-white md:hidden">
      {NAV_ITEMS.map(({ id, label, Icon }) => {
        const isActive = activeTab === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelectTab(id)}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2 ${isActive ? 'text-ink' : 'text-text-muted'}`}
          >
            <Icon />
            <span className={`text-xs ${isActive ? 'font-medium' : ''}`}>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}
