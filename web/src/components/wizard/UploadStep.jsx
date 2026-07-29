import { useState } from 'react';

export default function UploadStep({ onNext }) {
  const [storeId, setStoreId] = useState('');
  const [shelfId, setShelfId] = useState('');
  const [file, setFile] = useState(null);

  const canSubmit = storeId.trim() && shelfId.trim() && file;

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onNext({ storeId: storeId.trim(), shelfId: shelfId.trim(), file });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h2 className="text-lg font-semibold">1. Chọn ảnh kệ hàng</h2>
      <label className="block">
        <span className="text-sm font-medium">Store ID</span>
        <input
          type="text"
          value={storeId}
          onChange={(e) => setStoreId(e.target.value)}
          required
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Shelf ID</span>
        <input
          type="text"
          value={shelfId}
          onChange={(e) => setShelfId(e.target.value)}
          required
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Ảnh kệ hàng</span>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          required
          className="mt-1 block"
        />
      </label>
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
      >
        Tiếp tục
      </button>
    </form>
  );
}
