const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://127.0.0.1:8001';

// Calls ml-service POST /predict. Returns { image, boxes, warnings } on
// success, throws on network error or non-2xx response.
async function predict(buffer, filename, mimetype) {
  const form = new FormData();
  form.append('image', new Blob([buffer], { type: mimetype }), filename);

  const res = await fetch(`${ML_SERVICE_URL}/predict`, { method: 'POST', body: form });
  if (!res.ok) {
    throw new Error(`ml-service responded ${res.status} ${res.statusText}`);
  }
  return res.json();
}

module.exports = { predict, ML_SERVICE_URL };
