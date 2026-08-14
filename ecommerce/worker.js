// worker.js - Cloudflare Worker untuk toko e-commerce (tanpa build step)
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
};
function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...CORS } });
}
function error(msg, status = 400) { return json({ error: msg }, status); }
async function readBody(req) { try { return await req.json(); } catch { return {}; } }

// ---------- Auth admin ----------
async function importHmacKey(secret) {
  return crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']);
}
async function signToken(secret, payload) {
  const data = JSON.stringify(payload);
  const key = await importHmacKey(secret);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data));
  const sigB64 = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return btoa(data) + '.' + sigB64;
}
async function verifyToken(token, secret) {
  try {
    const [dataB64, sigB64] = token.split('.');
    if (!dataB64 || !sigB64) return null;
    const data = atob(dataB64);
    const key = await importHmacKey(secret);
    const sig = Uint8Array.from(atob(sigB64), c => c.charCodeAt(0));
    const ok = await crypto.subtle.verify('HMAC', key, sig, new TextEncoder().encode(data));
    if (!ok) return null;
    const payload = JSON.parse(data);
    if (!payload.exp || payload.exp < Date.now()) return null;
    return payload;
  } catch { return null; }
}
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
async function getTokenPayload(req, env) {
  const auth = req.headers.get('Authorization') || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (!m) return null;
  return verifyToken(m[1], env.ADMIN_SECRET);
}

// ---------- Helpers ----------
function calcTotal(items, shipping = 0) {
  return items.reduce((s, l) => s + l.price * l.qty, 0) + (shipping || 0);
}
function waLink(settings, order) {
  if (!settings.wa_number) return '';
  const items = order.items.map(i => `- ${i.name} x${i.qty}`).join('%0A');
  const msg = `Halo, saya pesan:%0A${items}%0ATotal: Rp${order.total + (order.shipping_cost||0)}%0AAlamat: ${order.address || '-'}%0AKode Pesanan: #${order.id}`;
  return `https://wa.me/${settings.wa_number}?text=${msg}`;
}

async function getSettings(env) {
  const s = await env.DB.prepare('SELECT * FROM settings WHERE id = 1').first();
  return s || {};
}

// ---------- API ----------
async function handleApi(req, env, url) {
  const method = req.method;
  const p = url.pathname;
  if (method === 'OPTIONS') return new Response(null, { headers: CORS });

  // ===== PUBLIC =====
  if (p === '/api/products' && method === 'GET') {
    const cat = url.searchParams.get('category');
    const q = url.searchParams.get('q');
    let sql = 'SELECT id, name, description, price, stock, image_url, category FROM products WHERE active = 1';
    const binds = [];
    if (cat && cat !== 'all') { sql += ' AND category = ?'; binds.push(cat); }
    if (q) { sql += ' AND (name LIKE ? OR description LIKE ?)'; binds.push('%'+q+'%', '%'+q+'%'); }
    sql += ' ORDER BY created_at DESC';
    const { results } = await env.DB.prepare(sql).bind(...binds).all();
    return json(results);
  }
  if (p === '/api/categories' && method === 'GET') {
    const { results } = await env.DB.prepare(
      "SELECT category, COUNT(*) as count FROM products WHERE active=1 GROUP BY category ORDER BY category"
    ).all();
    return json(results);
  }

  // Tracking pesanan publik (by id)
  if (p === '/api/track' && method === 'GET') {
    const id = Number(url.searchParams.get('id'));
    const row = await env.DB.prepare('SELECT id, status, payment_status, tracking_code, tracking_url, shipping_service, total, shipping_cost, created_at FROM orders WHERE id = ?').bind(id).first();
    if (!row) return error('Pesanan tidak ditemukan', 404);
    return json(row);
  }

  // Estimasi ongkir (flat / scaffold rajaongkir)
  if (p === '/api/shipping' && method === 'GET') {
    const settings = await getSettings(env);
    const dest = Number(url.searchParams.get('dest') || 0);
    const weight = Number(url.searchParams.get('weight') || 1000);
    const total = Number(url.searchParams.get('total') || 0);
    if (settings.free_shipping_min && total >= settings.free_shipping_min) {
      return json({ mode: settings.shipping_mode, cost: 0, free: true });
    }
    if (settings.shipping_mode === 'rajaongkir' && settings.rajaongkir_api_key && dest) {
      return json({ mode: 'rajaongkir', cost: Number(settings.flat_shipping), note: 'Hubungkan API RajaOngkir di admin' });
    }
    return json({ mode: settings.shipping_mode, cost: Number(settings.flat_shipping) });
  }

  // Buat pesanan (publik) dengan alamat + ongkir + metode bayar
  if (p === '/api/orders' && method === 'POST') {
    const b = await readBody(req);
    const name = (b.customer_name || '').toString().trim();
    const contact = (b.customer_contact || '').toString().trim();
    const items = Array.isArray(b.items) ? b.items : [];
    if (!name || !contact) return error('Nama dan kontak wajib diisi');
    if (items.length === 0) return error('Keranjang kosong');
    const address = (b.address || '').toString().trim();
    const city = (b.city || '').toString().trim();
    const postal = (b.postal_code || '').toString().trim();
    const shipping_cost = Number(b.shipping_cost) || 0;
    const shipping_service = (b.shipping_service || '').toString();
    const payment_method = (b.payment_method || 'qris').toString();

    let total = 0; const lines = [];
    for (const it of items) {
      const pid = Number(it.product_id);
      const qty = Math.max(1, Math.floor(Number(it.qty) || 1));
      const row = await env.DB.prepare('SELECT id, name, price, stock FROM products WHERE id = ? AND active = 1').bind(pid).first();
      if (!row) return error('Produk tidak ditemukan: ' + pid);
      if (row.stock < qty) return error('Stok tidak cukup untuk: ' + row.name);
      total += row.price * qty;
      lines.push({ product_id: pid, name: row.name, price: row.price, qty });
    }
    const grand = total + shipping_cost;
    const info = await env.DB.prepare(
      'INSERT INTO orders (customer_name, customer_contact, items, total, status, created_at, address, city, postal_code, shipping_cost, shipping_service, payment_method, payment_status, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
    ).bind(name, contact, JSON.stringify(lines), total, 'pending', Date.now(), address, city, postal, shipping_cost, shipping_service, payment_method, payment_method==='cod'?'paid':'unpaid', (b.notes||'').toString()).run();
    const orderId = info.meta.last_row_id;
    for (const l of lines) {
      await env.DB.prepare('UPDATE products SET stock = stock - ? WHERE id = ?').bind(l.qty, l.product_id).run();
    }
    const order = { id: orderId, total, shipping_cost, status: 'pending', payment_status: payment_method==='cod'?'paid':'unpaid' };
    const settings = await getSettings(env);
    // Jika payment gateway terhubung, buat invoice (scaffold)
    let payment = null;
    if (settings.payment_gateway === 'midtrans' && settings.midtrans_server_key) {
      // TODO: panggil Midtrans API untuk Snap token (perlu implementasi fetch ke api.midtrans.com)
      payment = { gateway: 'midtrans', note: 'Aktifkan di admin untuk mode Snap' };
    }
    return json({ ok: true, order_id: orderId, total: grand, wa_link: waLink({...settings, wa_number: settings.wa_number||''}, {...order, items: lines}), payment }, 201);
  }

  // ===== LOGIN ADMIN =====
  if (p === '/api/admin/login' && method === 'POST') {
    const b = await readBody(req);
    const pw = (b.password || '').toString();
    if (!env.ADMIN_PASSWORD || !timingSafeEqual(pw, env.ADMIN_PASSWORD)) return error('Password salah', 401);
    const token = await signToken(env.ADMIN_SECRET, { exp: Date.now() + 1000*60*60*24*7, role: 'admin' });
    return json({ token });
  }
  if (p === '/api/admin/settings' && method === 'GET') {
    const admin = await getTokenPayload(req, env); if (!admin) return error('Unauthorized', 401);
    const s = await getSettings(env);
    // jangan kirim secret key ke client
    const safe = { ...s }; delete safe.midtrans_server_key; delete safe.xendit_secret_key; delete safe.rajaongkir_api_key; delete safe.biteship_api_key;
    return json(safe);
  }

  // ===== ADMIN =====
  const admin = await getTokenPayload(req, env);
  if (!admin) return error('Unauthorized', 401);

  // Settings update
  if (p === '/api/admin/settings' && method === 'PUT') {
    const b = await readBody(req);
    const allowed = ['store_name','wa_number','qris_image_url','shipping_mode','flat_shipping','free_shipping_min','rajaongkir_api_key','rajaongkir_origin','biteship_api_key','payment_gateway','midtrans_server_key','midtrans_client_key','xendit_secret_key','xendit_public_key'];
    const sets = [], binds = [];
    for (const k of allowed) { if (b[k] !== undefined) { sets.push(`${k} = ?`); binds.push(b[k]); } }
    if (sets.length) { binds.push(1); await env.DB.prepare('UPDATE settings SET ' + sets.join(', ') + ' WHERE id = ?').bind(...binds).run(); }
    return json({ ok: true });
  }

  if (p === '/api/admin/products' && method === 'GET') {
    const { results } = await env.DB.prepare('SELECT * FROM products ORDER BY created_at DESC').all();
    return json(results);
  }
  if (p === '/api/admin/products' && method === 'POST') {
    const b = await readBody(req);
    const name = (b.name || '').toString().trim(); if (!name) return error('Nama produk wajib');
    await env.DB.prepare(
      'INSERT INTO products (name, description, price, stock, image_url, active, category, weight, sku, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)'
    ).bind(name, (b.description||'').toString(), Number(b.price)||0, Math.max(0,Math.floor(Number(b.stock)||0)),
      (b.image_url||'').toString(), b.active===false?0:1, (b.category||'Lainnya').toString(), Math.max(0,Math.floor(Number(b.weight)||500)),
      (b.sku||'').toString(), Date.now()).run();
    return json({ ok: true }, 201);
  }
  let m = p.match(/^\/api\/admin\/products\/(\d+)$/);
  if (m && method === 'PUT') {
    const id = Number(m[1]); const b = await readBody(req);
    const sets = [], binds = [];
    for (const f of ['name','description','price','stock','image_url','category','weight','sku']) {
      if (b[f] !== undefined) { sets.push(`${f} = ?`); binds.push(f==='stock'||f==='weight'?Math.max(0,Math.floor(Number(b[f]))):b[f].toString()); }
    }
    if (b.active !== undefined) { sets.push('active = ?'); binds.push(b.active?1:0); }
    if (!sets.length) return error('Tidak ada field diubah');
    binds.push(id);
    await env.DB.prepare('UPDATE products SET ' + sets.join(', ') + ' WHERE id = ?').bind(...binds).run();
    return json({ ok: true });
  }
  if (m && method === 'DELETE') {
    await env.DB.prepare('DELETE FROM products WHERE id = ?').bind(Number(m[1])).run();
    return json({ ok: true });
  }

  if (p === '/api/admin/orders' && method === 'GET') {
    const { results } = await env.DB.prepare('SELECT * FROM orders ORDER BY created_at DESC').all();
    return json(results);
  }
  m = p.match(/^\/api\/admin\/orders\/(\d+)\/status$/);
  if (m && method === 'PUT') {
    const b = await readBody(req);
    await env.DB.prepare('UPDATE orders SET status = ? WHERE id = ?').bind((b.status||'pending').toString(), Number(m[1])).run();
    return json({ ok: true });
  }
  // Update resi / tracking + payment status
  m = p.match(/^\/api\/admin\/orders\/(\d+)$/);
  if (m && method === 'PUT') {
    const id = Number(m[1]); const b = await readBody(req);
    const sets = [], binds = [];
    for (const f of ['status','payment_status','tracking_code','tracking_url','shipping_service','shipping_cost','notes']) {
      if (b[f] !== undefined) { sets.push(`${f} = ?`); binds.push(b[f].toString()); }
    }
    if (!sets.length) return error('Tidak ada field diubah');
    binds.push(id);
    await env.DB.prepare('UPDATE orders SET ' + sets.join(', ') + ' WHERE id = ?').bind(...binds).run();
    return json({ ok: true });
  }

  // Analytics
  if (p === '/api/admin/analytics' && method === 'GET') {
    const rev = await env.DB.prepare("SELECT COALESCE(SUM(total+shipping_cost),0) as revenue, COUNT(*) as orders FROM orders WHERE status NOT IN ('cancelled')").first();
    const byStatus = await env.DB.prepare('SELECT status, COUNT(*) as c FROM orders GROUP BY status').all();
    const top = await env.DB.prepare("SELECT p.name, SUM(json_extract(value,'$.qty')) as sold FROM orders, json_each(items) JOIN products p ON p.id = json_extract(value,'$.product_id') GROUP BY p.id ORDER BY sold DESC LIMIT 5").all();
    const low = await env.DB.prepare('SELECT id, name, stock FROM products WHERE stock <= 5 ORDER BY stock ASC').all();
    const productsCount = await env.DB.prepare('SELECT COUNT(*) as c FROM products').first();
    return json({ revenue: rev.revenue||0, orders: rev.orders||0, byStatus: byStatus.results, top: top.results, lowStock: low.results, products: productsCount.c||0 });
  }

  return error('Not found', 404);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) return handleApi(request, env, url);
    return env.ASSETS.fetch(request);
  },
};
