const fmt = n => 'Rp' + Number(n).toLocaleString('id-ID');
const $ = s => document.querySelector(s);
let TOKEN = localStorage.getItem('admin_token') || '';

function authHeaders(){ return { 'Content-Type': 'application/json', Authorization: 'Bearer ' + TOKEN }; }
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function toast(msg, ok=true){ const t=$('#toast'); if(!t) return; t.textContent=msg; t.style.background=ok?'var(--ok)':'var(--danger)'; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2200); }

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { ...authHeaders(), ...(opts.headers||{}) } });
  if (res.status === 401) { logout(); throw new Error('Sesi habis, login ulang'); }
  return res;
}

function showPanel() {
  $('#loginBox').classList.add('hidden');
  $('#adminPanel').classList.remove('hidden');
  loadProducts(); loadOrders();
}
function logout(){ TOKEN=''; localStorage.removeItem('admin_token'); location.reload(); }

$('#loginBtn').onclick = async () => {
  const res = await fetch('/api/admin/login', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ password: $('#pwd').value }) });
  const data = await res.json();
  if (!res.ok) { $('#loginErr').textContent = data.error || 'Gagal login'; return; }
  TOKEN = data.token; localStorage.setItem('admin_token', TOKEN);
  showPanel();
};
$('#logoutBtn').onclick = logout;

async function loadProducts() {
  const res = await api('/api/admin/products');
  const rows = await res.json();
  const tb = $('#prodTable tbody');
  if (!rows.length) { tb.innerHTML = '<tr><td colspan="5" class="muted">Belum ada produk.</td></tr>'; return; }
  tb.innerHTML = rows.map(p => `
    <tr data-id="${p.id}">
      <td>${escapeHtml(p.name)}</td>
      <td><input type="number" min="0" value="${p.price}" data-f="price"></td>
      <td><input type="number" min="0" value="${p.stock}" data-f="stock"></td>
      <td><span class="tag ${p.active?'on':'off'}" data-toggle>${p.active?'Tampil':'Sembunyi'}</span></td>
      <td>
        <button class="btn small primary" data-save>💾</button>
        <button class="btn small danger" data-del>🗑</button>
      </td>
    </tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr => {
    const id = Number(tr.dataset.id);
    tr.querySelector('[data-save]').onclick = async () => {
      const price = tr.querySelector('[data-f=price]').value;
      const stock = tr.querySelector('[data-f=stock]').value;
      await api('/api/admin/products/' + id, { method:'PUT', body: JSON.stringify({ price, stock }) });
      toast('Tersimpan');
    };
    tr.querySelector('[data-toggle]').onclick = async () => {
      const active = tr.querySelector('[data-toggle]').classList.contains('off');
      await api('/api/admin/products/' + id, { method:'PUT', body: JSON.stringify({ active }) });
      loadProducts();
    };
    tr.querySelector('[data-del]').onclick = async () => {
      if (!confirm('Hapus produk ini?')) return;
      await api('/api/admin/products/' + id, { method:'DELETE' });
      loadProducts();
    };
  });
}

$('#addBtn').onclick = async () => {
  const name = $('#p_name').value.trim();
  if (!name) return toast('Nama wajib', false);
  await api('/api/admin/products', { method:'POST', body: JSON.stringify({
    name, price: Number($('#p_price').value)||0, stock: Number($('#p_stock').value)||0,
    image_url: $('#p_img').value.trim(), description: $('#p_desc').value.trim(),
    active: $('#p_active').checked,
  }) });
  $('#p_name').value=''; $('#p_price').value=''; $('#p_stock').value=''; $('#p_img').value=''; $('#p_desc').value=''; $('#p_active').checked=true;
  toast('Produk ditambahkan');
  loadProducts();
};

async function loadOrders() {
  const res = await api('/api/admin/orders');
  const rows = await res.json();
  const box = $('#orderList');
  if (!rows.length) { box.innerHTML = '<p class="muted">Belum ada pesanan.</p>'; return; }
  const statusColors = { pending:'var(--warn)', paid:'var(--brand)', shipped:'#9b7bff', done:'var(--ok)', cancelled:'var(--danger)' };
  box.innerHTML = rows.map(o => {
    const items = JSON.parse(o.items || '[]');
    const list = items.map(i => `${escapeHtml(i.name)} ×${i.qty}`).join(', ');
    return `<div class="panel" style="padding:14px">
      <div class="row" style="justify-content:space-between">
        <b>#${o.id} · ${escapeHtml(o.customer_name)}</b>
        <span class="badge" style="color:${statusColors[o.status]||'var(--muted)'};font-weight:700">${o.status.toUpperCase()}</span>
      </div>
      <div class="muted">${escapeHtml(o.customer_contact)} · ${new Date(o.created_at).toLocaleString('id-ID')}</div>
      <div class="muted">${list}</div>
      <div style="margin-top:6px">Total: <b>${fmt(o.total)}</b></div>
      <div class="row" style="margin-top:8px;gap:6px">
        ${['pending','paid','shipped','done','cancelled'].map(s =>
          `<button class="btn small" data-status="${s}" data-id="${o.id}" style="${o.status===s?'border-color:var(--brand)':''}">${s}</button>`).join('')}
      </div>
    </div>`;
  }).join('');
  box.querySelectorAll('[data-status]').forEach(b => b.onclick = async () => {
    await api('/api/admin/orders/' + b.dataset.id + '/status', { method:'PUT', body: JSON.stringify({ status: b.dataset.status }) });
    loadOrders();
  });
}

// toast element
if (!$('#toast')) { const t=document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }

if (TOKEN) { showPanel(); }
