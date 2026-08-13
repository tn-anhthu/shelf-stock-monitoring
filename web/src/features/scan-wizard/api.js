export async function analyzeImage({ category, container, imageBlob, filename }) {
  const formData = new FormData();
  formData.append('category', category);
  formData.append('container', container);
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

export async function fetchShelves() {
  const res = await fetch('/shelves');
  if (!res.ok) {
    throw new Error(`shelves request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchDashboard({ category, container }) {
  const params = new URLSearchParams({ category, container });
  const res = await fetch(`/dashboard?${params}`);
  if (!res.ok) {
    throw new Error(`dashboard request failed: ${res.status}`);
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
