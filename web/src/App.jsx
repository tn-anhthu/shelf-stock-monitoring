import Sidebar from './shared/Sidebar.jsx';
import ScanPage from './pages/ScanPage.jsx';

export default function App() {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <Sidebar />
      <main className="flex-1 p-6">
        <ScanPage />
      </main>
    </div>
  );
}
