export default function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-white p-4">
      <h1 className="mb-6 text-lg font-bold">ShelfSense</h1>
      <nav className="space-y-1">
        <div className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white">Scan</div>
        <div className="cursor-not-allowed rounded px-3 py-2 text-sm text-slate-400" title="Sắp có">
          Dashboard <span className="text-xs">(sắp có)</span>
        </div>
      </nav>
    </aside>
  );
}
