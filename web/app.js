const form = document.getElementById('scan-form');
const statusMessage = document.getElementById('status-message');
const result = document.getElementById('result');
const boxesBody = document.querySelector('#boxes-table tbody');
const quantitiesBody = document.querySelector('#quantities-table tbody');
const totalValueEl = document.getElementById('total-value');

const currency = (n) => n.toLocaleString('vi-VN') + ' đ';

function renderBoxes(boxes) {
  boxesBody.innerHTML = '';
  for (const box of boxes) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${box.box_id}</td>
      <td>${box.type}</td>
      <td>${box.sku_name ?? '(chưa nhận diện)'}</td>
      <td>${box.confidence.toFixed(2)}</td>
      <td>${box.is_unknown ? 'có' : ''}</td>
    `;
    boxesBody.appendChild(row);
  }
}

function renderQuantities(quantities) {
  quantitiesBody.innerHTML = '';
  for (const q of quantities) {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${q.sku_name}</td>
      <td>${q.facing_count}/${q.shelf_full_qty}</td>
      <td>${currency(q.unit_price)}</td>
      <td>${currency(q.subtotal)}</td>
      <td class="flag-${q.flag_status}">${q.flag_status}</td>
    `;
    quantitiesBody.appendChild(row);
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  statusMessage.hidden = true;
  statusMessage.className = '';
  result.hidden = true;

  const formData = new FormData(form);

  let data;
  try {
    const res = await fetch('/analyze', { method: 'POST', body: formData });
    data = await res.json();
  } catch (err) {
    statusMessage.textContent = `Lỗi kết nối: ${err.message}`;
    statusMessage.className = 'status-failed';
    statusMessage.hidden = false;
    return;
  }

  if (data.status === 'failed') {
    statusMessage.textContent = `Quét thất bại: ${data.error_message}`;
    statusMessage.className = 'status-failed';
    statusMessage.hidden = false;
    return;
  }

  if (data.status === 'partial') {
    statusMessage.textContent = 'Có sản phẩm chưa nhận diện được trên kệ — kiểm tra lại thủ công.';
    statusMessage.className = 'status-partial';
    statusMessage.hidden = false;
  }

  renderBoxes(data.boxes);
  renderQuantities(data.quantities);
  totalValueEl.textContent = `Tổng giá trị: ${currency(data.total_value)}`;
  result.hidden = false;
});
