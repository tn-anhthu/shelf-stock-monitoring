import { useEffect, useState } from 'react';
import Sidebar from './shared/Sidebar.jsx';
import BottomNav from './shared/BottomNav.jsx';
import ScanPage from './pages/ScanPage.jsx';

const SIDEBAR_COLLAPSED_KEY = 'shelfsense_sidebar_collapsed';

export default function App() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true',
  );

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  return (
    <div className="flex min-h-screen bg-page text-ink">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((prev) => !prev)} />
      <main className="flex-1 p-4 pb-20 md:p-6 md:pb-6">
        <ScanPage />
      </main>
      <BottomNav />
    </div>
  );
}
