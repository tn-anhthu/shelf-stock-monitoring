export async function analyzeImage({ storeId, shelfId, imageBlob, filename }) {
  const formData = new FormData();
  formData.append('store_id', storeId);
  formData.append('shelf_id', shelfId);
  formData.append('image', imageBlob, filename || 'shelf.jpg');

  const res = await fetch('/analyze', { method: 'POST', body: formData });
  if (!res.ok) {
    throw new Error(`analyze request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchCatalog() {
  const res = await fetch('/catalog');
  if (!res.ok) {
    throw new Error(`catalog request failed: ${res.status}`);
  }
  return res.json();
}

export async function confirmScan(payload) {
  const res = await fetch('/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `confirm request failed: ${res.status}`);
  }
  return res.json();
}
