const fmt = n => 'Rp' + Number(n).toLocaleString('id-ID');
const $ = s => document.querySelector(s);
const cart = {}; // id -> {product, qty}

function toast(msg, ok = true) {
  const t = $('#toast');
  t.textContent = msg;
  t.style.background = ok ? 'var(--ok)' : 'var(--danger)';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}

async function loadProducts() {
  const res = await fetch('/api/products');
  const items = await res.json();
  const grid = $('#productGrid');
  if (!items.length) { grid.innerHTML = '<div class="empty">Belum ada produk.</div>'; return; }
  grid.innerHTML = items.map(p => {
    const out = p.stock <= 0;
    const thumb = p.image_url
      ? `<div class="thumb" style="background-image:url('${p.image_url}')"></div>`
      : `<div class="thumb">📦 ${p.name}</div>`;
    return `<div class="card" data-id="${p.id}">
      ${thumb}
      <div class="body">
        <h3>${escapeHtml(p.name)}</h3>
        <div class="desc">${escapeHtml(p.description || '')}</div>
        <div class="price">${fmt(p.price)}</div>
        <div class="stock ${out ? 'out' : ''}">${out ? 'Stok habis' : 'Stok: ' + p.stock}</div>
        ${out ? '<button class="btn" disabled>Habis</button>' : `
          <div class="row">
            <div class="qty">
              <button data-act="dec">−</button>
              <input type="number" min="1" max="${p.stock}" value="1" data-id="${p.id}">
              <button data-act="inc">+</button>
            </div>
            <button class="btn primary" data-act="add" style="flex:1">+ Keranjang</button>
          </div>`}
      </div>
    </div>`;
  }).join('');

  grid.querySelectorAll('[data-act]').forEach(el => {
    el.addEventListener('click', e => {
      const card = el.closest('.card');
      const id = Number(card.dataset.id);
      const product = items.find(x => x.id === id);
      if (el.dataset.act === 'add') {
        const qty = Math.max(1, Math.min(product.stock, Number(card.querySelector('input').value) || 1));
        addToCart(product, qty);
      } else if (el.dataset.act === 'inc') {
        const inp = card.querySelector('input');
        inp.value = Math.min(product.stock, Number(inp.value) + 1);
      } else if (el.dataset.act === 'dec') {
        const inp = card.querySelector('input');
        inp.value = Math.max(1, Number(inp.value) - 1);
      }
    });
  });
}

function addToCart(product, qty) {
  if (cart[product.id]) cart[product.id].qty = Math.min(product.stock, cart[product.id].qty + qty);
  else cart[product.id] = { product, qty };
  renderCart();
  toast('Ditambahkan ke keranjang');
}

function changeQty(id, d) {
  if (!cart[id]) return;
  cart[id].qty = Math.max(1, cart[id].qty + d);
  renderCart();
}

function renderCart() {
  const ids = Object.keys(cart);
  $('#cartCount').style.display = ids.length ? 'flex' : 'none';
  $('#cartCount').textContent = ids.reduce((s, id) => s + cart[id].qty, 0);
  const box = $('#cartItems');
  if (!ids.length) { box.innerHTML = '<div class="empty">Keranjang kosong</div>'; $('#cartTotal').textContent = fmt(0); return; }
  box.innerHTML = ids.map(id => {
    const c = cart[id];
    return `<div class="citem">
      <div class="meta"><b>${escapeHtml(c.product.name)}</b><br><small>${fmt(c.product.price)} × ${c.qty}</small></div>
      <div class="ctrl">
        <button class="btn small" data-dec="${id}">−</button>
        <span>${c.qty}</span>
        <button class="btn small" data-inc="${id}">+</button>
        <button class="btn danger small" data-del="${id}">✕</button>
      </div>
    </div>`;
  }).join('');
  const total = ids.reduce((s, id) => s + cart[id].product.price * cart[id].qty, 0);
  $('#cartTotal').textContent = fmt(total);
  box.querySelectorAll('[data-dec]').forEach(b => b.onclick = () => changeQty(Number(b.dataset.dec), -1));
  box.querySelectorAll('[data-inc]').forEach(b => b.onclick = () => changeQty(Number(b.dataset.inc), 1));
  box.querySelectorAll('[data-del]').forEach(b => b.onclick = () => { delete cart[b.dataset.del]; renderCart(); });
}

async function checkout() {
  const name = $('#custName').value.trim();
  const contact = $('#custContact').value.trim();
  if (!name || !contact) return toast('Isi nama & kontak dulu', false);
  const ids = Object.keys(cart);
  if (!ids.length) return toast('Keranjang kosong', false);
  const items = ids.map(id => ({ product_id: Number(id), qty: cart[id].qty }));
  const btn = $('#checkoutBtn'); btn.disabled = true; btn.textContent = 'Mengirim…';
  const res = await fetch('/api/orders', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ customer_name: name, customer_contact: contact, items }),
  });
  const data = await res.json();
  btn.disabled = false; btn.textContent = 'Pesan Sekarang';
  if (!res.ok) return toast(data.error || 'Gagal memesan', false);
  toast('Pesanan terkirim! Total ' + fmt(data.total));
  for (const id of ids) delete cart[id];
  renderCart();
  $('#custName').value = ''; $('#custContact').value = '';
  closeCart();
}

function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

function openCart(){ $('#drawer').classList.add('open'); $('#drawerBack').classList.add('show'); }
function closeCart(){ $('#drawer').classList.remove('open'); $('#drawerBack').classList.remove('show'); }

$('#openCart').onclick = openCart;
$('#drawerBack').onclick = closeCart;
$('#checkoutBtn').onclick = checkout;
loadProducts();
