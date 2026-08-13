import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchShelves, fetchDashboard } from '../features/scan-wizard/api.js';
import CategoryContainerPicker from '../features/inventory/CategoryContainerPicker.jsx';
import StatusBar from '../features/inventory/StatusBar.jsx';
import SkuTable from '../features/inventory/SkuTable.jsx';
import Totals from '../features/inventory/Totals.jsx';
import EmptyState from '../features/inventory/EmptyState.jsx';
import ErrorBanner from '../features/inventory/ErrorBanner.jsx';
import { buildAttentionFirstRows } from '../features/inventory/sortRows.js';

export default function InventoryPage({ onScanShelf }) {
  const [categories, setCategories] = useState(null);
  const [category, setCategory] = useState(null);
  const [container, setContainer] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchShelves()
      .then(({ categories: cats }) => {
        setCategories(cats);
        const firstActiveCategory = cats.find((c) => c.active);
        const firstActiveContainer = firstActiveCategory?.containers.find((c) => c.active);
        setCategory(firstActiveCategory?.slug ?? null);
        setContainer(firstActiveContainer?.id ?? null);
      })
      .catch((err) => setError(err.message));
  }, []);

  const loadDashboard = useCallback(() => {
    if (!category || !container) return;
    setLoading(true);
    setError(null);
    fetchDashboard({ category, container })
      .then(setDashboard)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [category, container]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  function handleCategoryChange(slug) {
    setCategory(slug);
    const nextCategory = categories.find((c) => c.slug === slug);
    const firstActiveContainer = nextCategory?.containers.find((c) => c.active);
    setContainer(firstActiveContainer?.id ?? null);
  }

  const rows = useMemo(() => buildAttentionFirstRows(dashboard), [dashboard]);
  const selectedCategory = categories?.find((c) => c.slug === category);
  const selectedContainer = selectedCategory?.containers.find((c) => c.id === container);

  return (
    <div className="mx-auto max-w-4xl">
      <header className="flex items-baseline justify-between gap-4 border-b border-card-border pb-4">
        <div>
          <h1 className="font-heading text-xl font-bold text-ink">Tình trạng kệ hàng</h1>
          <p className="mt-1 text-xs text-text-secondary">Tồn kho khu trưng bày — cập nhật theo lần scan gần nhất</p>
        </div>
        {selectedCategory && selectedContainer && (
          <button
            type="button"
            onClick={() => onScanShelf({ category, container })}
            className="whitespace-nowrap text-xs text-text-secondary underline decoration-1 underline-offset-2 hover:text-ink"
          >
            Scan lại kệ này
          </button>
        )}
      </header>

      {!categories ? (
        <p className="py-16 text-center text-sm text-text-muted">Đang tải…</p>
      ) : (
        <div className="mt-4 space-y-6">
          <CategoryContainerPicker
            categories={categories}
            category={category}
            container={container}
            onCategoryChange={handleCategoryChange}
            onContainerChange={setContainer}
          />

          {loading && <p className="py-16 text-center text-sm text-text-muted">Đang tải dữ liệu kệ hàng…</p>}

          {!loading && error && <ErrorBanner message={error} onRetry={loadDashboard} />}

          {!loading && !error && dashboard && !dashboard.has_data && (
            <EmptyState onScanNow={() => onScanShelf({ category, container })} />
          )}

          {!loading && !error && dashboard?.has_data && (
            <>
              <StatusBar {...dashboard.status_breakdown} />
              <SkuTable rows={rows} />
              <Totals kpis={dashboard.kpis} />
            </>
          )}
        </div>
      )}
    </div>
  );
}
