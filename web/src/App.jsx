import Sidebar from './shared/Sidebar.jsx';
import BottomNav from './shared/BottomNav.jsx';
import ScanPage from './pages/ScanPage.jsx';

export default function App() {
  return (
    <div className="flex min-h-screen bg-page text-ink">
      <Sidebar />
      <main className="flex-1 p-4 pb-20 md:p-6 md:pb-6">
        <ScanPage />
      </main>
      <BottomNav />
    </div>
  );
}
