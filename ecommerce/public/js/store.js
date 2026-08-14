const fmt = n => 'Rp' + Number(n).toLocaleString('id-ID');
const $ = s => document.querySelector(s);
const cart = {};
let PRODUCTS = [];
let SETTINGS = {};
let currentCat = 'all';
let currentQ = '';
let shippingCost = 0;

function toast(msg, ok = true) {
  const t = $('#toast'); t.textContent = msg;
  t.style.background = ok ? 'var(--ok)' : 'var(--danger)';
  t.classList.add('show'); setTimeout(() => t.classList.remove('show'), 2200);
}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

async function loadSettings() {
  try {
    const s = await (await fetch('/api/admin/settings')).json();
    SETTINGS = s || {};
    if (SETTINGS.store_name) $('#storeName').innerHTML = escapeHtml(SETTINGS.store_name).replace(' ','<span>') + '</span>';
  } catch { SETTINGS = {}; }
}

async function loadCategories() {
  try {
    const cats = await (await fetch('/api/categories')).json();
    const box = $('#cats');
    box.innerHTML = '<span class="chip active" data-cat="all">Semua</span>' +
      cats.map(c => `<span class="chip" data-cat="${escapeHtml(c.category)}">${escapeHtml(c.category)} (${c.count})</span>`).join('');
    box.querySelectorAll('.chip').forEach(ch => ch.onclick = () => {
      box.querySelectorAll('.chip').forEach(x => x.classList.remove('active'));
      ch.classList.add('active'); currentCat = ch.dataset.cat; renderProducts();
    });
  } catch {}
}

async function loadProducts() {
  const res = await fetch('/api/products?category=' + encodeURIComponent(currentCat) + '&q=' + encodeURIComponent(currentQ));
  PRODUCTS = await res.json();
  renderProducts();
}

function renderProducts() {
  const grid = $('#productGrid');
  if (!PRODUCTS.length) { grid.innerHTML = '<div class="empty">Tidak ada produk.</div>'; return; }
  grid.innerHTML = PRODUCTS.map(p => {
    const out = p.stock <= 0;
    const thumb = p.image_url
      ? `<div class="thumb" style="background-image:url('${p.image_url}')"></div>`
      : `<div class="thumb">📦 ${escapeHtml(p.name)}</div>`;
    return `<div class="card" data-id="${p.id}">
      ${thumb}
      <div class="body">
        <h3>${escapeHtml(p.name)}</h3>
        <div class="desc">${escapeHtml(p.description || '')}</div>
        ${p.category ? `<span class="tag off">${escapeHtml(p.category)}</span>` : ''}
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
  grid.querySelectorAll('[data-act]').forEach(el => el.onclick = () => {
    const card = el.closest('.card'); const id = Number(card.dataset.id);
    const product = PRODUCTS.find(x => x.id === id);
    if (el.dataset.act === 'add') {
      const qty = Math.max(1, Math.min(product.stock, Number(card.querySelector('input').value) || 1));
      addToCart(product, qty);
    } else if (el.dataset.act === 'inc') { const i = card.querySelector('input'); i.value = Math.min(product.stock, Number(i.value)+1); }
    else if (el.dataset.act === 'dec') { const i = card.querySelector('input'); i.value = Math.max(1, Number(i.value)-1); }
  });
}

function addToCart(product, qty) {
  if (cart[product.id]) cart[product.id].qty = Math.min(product.stock, cart[product.id].qty + qty);
  else cart[product.id] = { product, qty };
  renderCart(); toast('Ditambahkan ke keranjang');
  estimateShipping();
}
function changeQty(id, d) { if (!cart[id]) return; cart[id].qty = Math.max(1, cart[id].qty + d); renderCart(); estimateShipping(); }

function renderCart() {
  const ids = Object.keys(cart);
  $('#cartCount').style.display = ids.length ? 'flex' : 'none';
  $('#cartCount').textContent = ids.reduce((s,id)=>s+cart[id].qty,0);
  const box = $('#cartItems');
  if (!ids.length) { box.innerHTML = '<div class="empty">Keranjang kosong</div>'; $('#cartTotal').textContent = fmt(0); updateGrand(); return; }
  box.innerHTML = ids.map(id => {
    const c = cart[id];
    return `<div class="citem"><div class="meta"><b>${escapeHtml(c.product.name)}</b><br><small>${fmt(c.product.price)} × ${c.qty}</small></div>
      <div class="ctrl"><button class="btn small" data-dec="${id}">−</button><span>${c.qty}</span><button class="btn small" data-inc="${id}">+</button><button class="btn danger small" data-del="${id}">✕</button></div></div>`;
  }).join('');
  const total = ids.reduce((s,id)=>s+cart[id].product.price*cart[id].qty,0);
  $('#cartTotal').textContent = fmt(total);
  box.querySelectorAll('[data-dec]').forEach(b=>b.onclick=()=>changeQty(Number(b.dataset.dec),-1));
  box.querySelectorAll('[data-inc]').forEach(b=>b.onclick=()=>changeQty(Number(b.dataset.inc),1));
  box.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>{delete cart[b.dataset.del];renderCart();estimateShipping();});
  updateGrand();
}

function subtotal() { return Object.keys(cart).reduce((s,id)=>s+cart[id].product.price*cart[id].qty,0); }
function updateGrand() { $('#grandTotal').textContent = fmt(subtotal() + shippingCost); }

async function estimateShipping() {
  const total = subtotal();
  const sel = $('#shipService');
  try {
    const r = await fetch('/api/shipping?total=' + total).then(x=>x.json());
    shippingCost = r.cost || 0;
    if (r.free) { sel.innerHTML = '<option value="Gratis">Gratis Ongkir</option>'; sel.value='Gratis'; }
    else { sel.innerHTML = `<option value="Reguler">Reguler (${fmt(r.cost)})</option>`; sel.value='Reguler'; }
  } catch { shippingCost = 0; }
  $('#shipCost').textContent = fmt(shippingCost);
  updateGrand();
}

async function checkout() {
  const name = $('#custName').value.trim();
  const contact = $('#custContact').value.trim();
  if (!name || !contact) return toast('Isi nama & kontak dulu', false);
  const ids = Object.keys(cart);
  if (!ids.length) return toast('Keranjang kosong', false);
  if (!$('#custAddr').value.trim()) return toast('Isi alamat pengiriman', false);
  const items = ids.map(id => ({ product_id: Number(id), qty: cart[id].qty }));
  const method = $('#payMethod').value;
  const btn = $('#checkoutBtn'); btn.disabled = true; btn.textContent = 'Mengirim…';
  const res = await fetch('/api/orders', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ customer_name:name, customer_contact:contact, items,
      address:$('#custAddr').value.trim(), city:$('#custCity').value.trim(), postal_code:$('#custPos').value.trim(),
      shipping_cost: shippingCost, shipping_service: $('#shipService').value, payment_method: method }) });
  const data = await res.json(); btn.disabled=false; btn.textContent='Pesan Sekarang';
  if (!res.ok) return toast(data.error || 'Gagal memesan', false);
  if (method === 'qris' && SETTINGS.qris_image_url) { showQris(data, name, contact, $('#custAddr').value); }
  else if (data.wa_link) { toast('Pesanan #'+data.order_id+'! Mengarahkan ke WhatsApp…'); window.open(data.wa_link,'_blank'); }
  else { toast('Pesanan #'+data.order_id+' terkirim!'); }
  for (const id of ids) delete cart[id];
  renderCart(); $('#custName').value=''; $('#custContact').value=''; $('#custAddr').value=''; $('#custCity').value=''; $('#custPos').value='';
  closeCart();
}

function showQris(data, name, contact, addr) {
  $('#qrisBody').innerHTML = `<p>Pesanan #<b>${data.order_id}</b> · Total <b>${fmt(data.total)}</b></p>
    <img src="${SETTINGS.qris_image_url}" style="max-width:220px;width:100%;border:1px solid var(--line);border-radius:10px">
    <p class="muted">Scan QRIS dengan e-wallet/mbanking. Admin akan konfirmasi manual.</p>`;
  $('#qrisModal').classList.add('show');
}

function openCart(){ $('#drawer').classList.add('open'); $('#drawerBack').classList.add('show'); }
function closeCart(){ $('#drawer').classList.remove('open'); $('#drawerBack').classList.remove('show'); }

// Tracking
function openTrack(){ $('#trackModal').classList.add('show'); }
async function doTrack() {
  const id = $('#trackId').value.trim();
  if (!id) return toast('Masukkan ID pesanan', false);
  const r = await fetch('/api/track?id=' + id).then(x=>x.json());
  if (r.error) { $('#trackResult').innerHTML = '<p class="muted">'+r.error+'</p>'; return; }
  const steps = ['pending','paid','shipped','done'];
  const idx = steps.indexOf(r.status);
  $('#trackResult').innerHTML = `<div class="track-steps">
    ${steps.map((s,i)=>`<div class="step ${i<=idx?'on':''}"><div class="dot"></div><span>${s.toUpperCase()}</span></div>`).join('<div class="line"></div>')}
  </div>
  <p>Status: <b>${r.status.toUpperCase()}</b> · Bayar: <b>${r.payment_status.toUpperCase()}</b></p>
  ${r.tracking_code ? `<p>No Resi: <b>${escapeHtml(r.tracking_code)}</b> ${r.tracking_url?`<a href="${r.tracking_url}" target="_blank">[Lacak]</a>`:''}</p>`:''}
  <p class="muted">Total: ${fmt(r.total + (r.shipping_cost||0))}</p>`;
}

$('#openCart').onclick = openCart;
$('#drawerBack').onclick = closeCart;
$('#checkoutBtn').onclick = checkout;
$('#trackBtn').onclick = openTrack;
$('#trackGo').onclick = doTrack;
$('#trackClose').onclick = () => $('#trackModal').classList.remove('show');
$('#payMethod').onchange = estimateShipping;
$('#qrisClose').onclick = () => $('#qrisModal').classList.remove('show');
$('#search').oninput = debounce(() => { currentQ = $('#search').value.trim(); loadProducts(); }, 300);

function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a),ms); }; }

loadSettings(); loadCategories(); loadProducts();
