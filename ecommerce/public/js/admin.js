const fmt = n => 'Rp' + Number(n).toLocaleString('id-ID');
const $ = s => document.querySelector(s);
let TOKEN = localStorage.getItem('admin_token') || '';
function authHeaders(){ return { 'Content-Type':'application/json', Authorization:'Bearer '+TOKEN }; }
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function toast(msg,ok=true){ const t=$('#toast'); if(!t) return; t.textContent=msg; t.style.background=ok?'var(--ok)':'var(--danger)'; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),2200); }
async function api(path, opts={}){ const res=await fetch(path,{...opts,headers:{...authHeaders(),...(opts.headers||{})}}); if(res.status===401){logout();throw new Error('Sesi habis');} return res; }

function showPanel(){ $('#loginBox').classList.add('hidden'); $('#adminPanel').classList.remove('hidden'); loadProducts(); loadOrders(); loadSettings(); loadAnalytics(); }
function logout(){ TOKEN=''; localStorage.removeItem('admin_token'); location.reload(); }

// Tabs
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.tabpane').forEach(x=>x.classList.add('hidden'));
  t.classList.add('active'); $('#tab-'+t.dataset.tab).classList.remove('hidden');
  if(t.dataset.tab==='analytics') loadAnalytics();
  if(t.dataset.tab==='pesanan') loadOrders();
});

$('#loginBtn').onclick = async () => {
  const res = await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#pwd').value})});
  const d = await res.json();
  if(!res.ok){ $('#loginErr').textContent=d.error||'Gagal'; return; }
  TOKEN=d.token; localStorage.setItem('admin_token',TOKEN); showPanel();
};
$('#logoutBtn').onclick = logout;

// ===== PRODUK =====
async function loadProducts(){
  const res = await api('/api/admin/products'); const rows = await res.json();
  const tb = $('#prodTable tbody');
  if(!rows.length){ tb.innerHTML='<tr><td colspan="6" class="muted">Belum ada produk.</td></tr>'; return; }
  tb.innerHTML = rows.map(p=>`<tr data-id="${p.id}">
    <td>${escapeHtml(p.name)}</td><td><span class="tag off">${escapeHtml(p.category||'')}</span></td>
    <td><input type="number" min="0" value="${p.price}" data-f="price"></td>
    <td><input type="number" min="0" value="${p.stock}" data-f="stock"></td>
    <td><span class="tag ${p.active?'on':'off'}" data-toggle>${p.active?'Tampil':'Sembunyi'}</span></td>
    <td><button class="btn small primary" data-save>💾</button><button class="btn small" data-edit>✏️</button><button class="btn small danger" data-del>🗑</button></td>
  </tr>`).join('');
  tb.querySelectorAll('tr').forEach(tr=>{
    const id=Number(tr.dataset.id);
    tr.querySelector('[data-save]').onclick=async()=>{ await api('/api/admin/products/'+id,{method:'PUT',body:JSON.stringify({price:tr.querySelector('[data-f=price]').value,stock:tr.querySelector('[data-f=stock]').value})}); toast('Tersimpan'); };
    tr.querySelector('[data-toggle]').onclick=async()=>{ const active=tr.querySelector('[data-toggle]').classList.contains('off'); await api('/api/admin/products/'+id,{method:'PUT',body:JSON.stringify({active})}); loadProducts(); };
    tr.querySelector('[data-edit]').onclick=()=>openEdit(id,rows.find(r=>r.id===id));
    tr.querySelector('[data-del]').onclick=async()=>{ if(!confirm('Hapus produk?')) return; await api('/api/admin/products/'+id,{method:'DELETE'}); loadProducts(); };
  });
}

function openEdit(id,p){
  $('#e_id').value=id; $('#e_name').value=p.name; $('#e_price').value=p.price; $('#e_stock').value=p.stock;
  $('#e_cat').value=p.category||''; $('#e_weight').value=p.weight||500; $('#e_sku').value=p.sku||'';
  $('#e_img').value=p.image_url||''; $('#e_desc').value=p.description||''; $('#e_active').checked=!!p.active;
  $('#editModal').classList.add('show');
}
$('#closeEdit').onclick=()=>$('#editModal').classList.remove('show');
$('#saveEdit').onclick=async()=>{
  const id=$('#e_id').value;
  await api('/api/admin/products/'+id,{method:'PUT',body:JSON.stringify({
    name:$('#e_name').value, price:$('#e_price').value, stock:$('#e_stock').value, category:$('#e_cat').value,
    weight:$('#e_weight').value, sku:$('#e_sku').value, image_url:$('#e_img').value, description:$('#e_desc').value, active:$('#e_active').checked })});
  $('#editModal').classList.remove('show'); toast('Produk diperbarui'); loadProducts();
};

$('#addBtn').onclick = async () => {
  const name=$('#p_name').value.trim(); if(!name) return toast('Nama wajib',false);
  await api('/api/admin/products',{method:'POST',body:JSON.stringify({
    name, price:Number($('#p_price').value)||0, stock:Number($('#p_stock').value)||0, category:$('#p_cat').value.trim()||'Lainnya',
    weight:Number($('#p_weight').value)||500, sku:$('#p_sku').value.trim(), image_url:$('#p_img').value.trim(),
    description:$('#p_desc').value.trim(), active:$('#p_active').checked })});
  ['p_name','p_price','p_stock','p_cat','p_weight','p_sku','p_img','p_desc'].forEach(i=>$('#'+i).value='');
  $('#p_active').checked=true; toast('Produk ditambahkan'); loadProducts();
};

// ===== PESANAN =====
async function loadOrders(){
  const res = await api('/api/admin/orders'); const rows = await res.json();
  const box=$('#orderList');
  if(!rows.length){ box.innerHTML='<p class="muted">Belum ada pesanan.</p>'; return; }
  const sc={pending:'var(--warn)',paid:'var(--brand)',shipped:'#9b7bff',done:'var(--ok)',cancelled:'var(--danger)'};
  box.innerHTML = rows.map(o=>{
    const items=JSON.parse(o.items||'[]');
    const list=items.map(i=>`${escapeHtml(i.name)} ×${i.qty}`).join(', ');
    return `<div class="panel" style="padding:14px">
      <div class="row" style="justify-content:space-between"><b>#${o.id} · ${escapeHtml(o.customer_name)}</b>
        <span class="badge" style="color:${sc[o.status]||'var(--muted)'};font-weight:700">${o.status.toUpperCase()}</span></div>
      <div class="muted">${escapeHtml(o.customer_contact)} · ${o.city||''} ${o.postal_code||''}</div>
      <div class="muted">${list}</div>
      <div class="muted">Alamat: ${escapeHtml(o.address||'-')}</div>
      <div>Total: <b>${fmt(o.total+(o.shipping_cost||0))}</b> · Ongkir ${fmt(o.shipping_cost||0)} · Bayar: <b>${o.payment_status}</b> · ${escapeHtml(o.payment_method||'')}</div>
      <div class="field" style="margin-top:8px"><label>No Resi</label><input id="resi-${o.id}" value="${escapeHtml(o.tracking_code||'')}" placeholder="Masukkan no resi"></div>
      <div class="field"><label>URL Lacak (opsional)</label><input id="turl-${o.id}" value="${escapeHtml(o.tracking_url||'')}" placeholder="https://..."></div>
      <div class="row" style="margin-top:6px;gap:6px;flex-wrap:wrap">
        ${['pending','paid','shipped','done','cancelled'].map(s=>`<button class="btn small" data-st="${s}" data-id="${o.id}" style="${o.status===s?'border-color:var(--brand)':''}">${s}</button>`).join('')}
        <button class="btn small primary" data-saveresi="${o.id}">Simpan Resi</button>
      </div></div>`;
  }).join('');
  box.querySelectorAll('[data-st]').forEach(b=>b.onclick=async()=>{ await api('/api/admin/orders/'+b.dataset.id+'/status',{method:'PUT',body:JSON.stringify({status:b.dataset.st})}); loadOrders(); });
  box.querySelectorAll('[data-saveresi]').forEach(b=>b.onclick=async()=>{
    const id=b.dataset.saveresi;
    await api('/api/admin/orders/'+id,{method:'PUT',body:JSON.stringify({tracking_code:$('#resi-'+id).value.trim(), tracking_url:$('#turl-'+id).value.trim(), status:'shipped'})});
    toast('Resi disimpan & status=shipped'); loadOrders();
  });
}

// ===== SETTINGS =====
async function loadSettings(){
  try{
    const s = await api('/api/admin/settings').then(r=>r.json());
    if(s.store_name) $('#brandName').innerHTML=escapeHtml(s.store_name).replace(' ','<span>')+'</span>';
    $('#s_store').value=s.store_name||''; $('#s_wa').value=s.wa_number||''; $('#s_qris').value=s.qris_image_url||'';
    $('#s_shipmode').value=s.shipping_mode||'flat'; $('#s_flat').value=s.flat_shipping||0; $('#s_free').value=s.free_shipping_min||0;
    $('#s_pg').value=s.payment_gateway||'manual'; $('#s_mid_c').value=s.midtrans_client_key||''; $('#s_xen_p').value=s.xendit_public_key||'';
    $('#s_raja').value=s.rajaongkir_api_key||''; $('#s_origin').value=s.rajaongkir_origin||'';
  }catch{}
}
$('#saveSettings').onclick=async()=>{
  await api('/api/admin/settings',{method:'PUT',body:JSON.stringify({
    store_name:$('#s_store').value, wa_number:$('#s_wa').value, qris_image_url:$('#s_qris').value,
    shipping_mode:$('#s_shipmode').value, flat_shipping:Number($('#s_flat').value)||0, free_shipping_min:Number($('#s_free').value)||0,
    payment_gateway:$('#s_pg').value, midtrans_server_key:$('#s_mid_s').value, midtrans_client_key:$('#s_mid_c').value,
    xendit_secret_key:$('#s_xen_s').value, xendit_public_key:$('#s_xen_p').value, rajaongkir_api_key:$('#s_raja').value, rajaongkir_origin:Number($('#s_origin').value)||0 })});
  toast('Pengaturan disimpan');
};

// ===== ANALYTICS =====
async function loadAnalytics(){
  const promises = []; // already inside try at caller
  try{
    const d = await api('/api/admin/analytics').then(r=>r.json());
    $('#statCards').innerHTML = `
      <div class="stat"><div class="stat-v">${fmt(d.revenue)}</div><div class="stat-l">Pendapatan</div></div>
      <div class="stat"><div class="stat-v">${d.orders}</div><div class="stat-l">Pesanan</div></div>
      <div class="stat"><div class="stat-v">${d.products}</div><div class="stat-l">Produk</div></div>`;
    $('#byStatus').innerHTML = (d.byStatus||[]).map(s=>`<div class="row" style="justify-content:space-between"><span>${s.status}</span><b>${s.c}</b></div>`).join('') || '<p class="muted">-</p>';
    $('#topProd').innerHTML = (d.top||[]).map(p=>`<div class="row" style="justify-content:space-between"><span>${escapeHtml(p.name)}</span><b>${p.sold} terjual</b></div>`).join('') || '<p class="muted">-</p>';
    $('#lowStock').innerHTML = (d.lowStock||[]).map(p=>`<div class="row" style="justify-content:space-between"><span>${escapeHtml(p.name)}</span><b style="color:var(--danger)">${p.stock}</b></div>`).join('') || '<p class="muted">Stok aman</p>';
  }catch(e){}
}

if(!$('#toast')){ const t=document.createElement('div'); t.id='toast'; t.className='toast'; document.body.appendChild(t); }
if(TOKEN) showPanel();
