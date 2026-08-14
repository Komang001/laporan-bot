// worker.js - Cloudflare Worker untuk toko e-commerce (tanpa build step)
// Menangani API + menyajikan asset statis dari folder public/ (via binding ASSETS).

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS },
  });
}
function error(msg, status = 400) {
  return json({ error: msg }, status);
}

async function readBody(req) {
  try { return await req.json(); } catch { return {}; }
}

// ---------- Auth admin (HMAC signed token, Web Crypto) ----------
async function importHmacKey(secret) {
  return crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify']
  );
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
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
async function getTokenPayload(req, env) {
  const auth = req.headers.get('Authorization') || '';
  const m = auth.match(/^Bearer\s+(.+)$/i);
  if (!m) return null;
  return verifyToken(m[1], env.ADMIN_SECRET);
}

// ---------- API ----------
async function handleApi(req, env, url) {
  const method = req.method;
  const p = url.pathname;

  if (method === 'OPTIONS') return new Response(null, { headers: CORS });

  // ===== PUBLIC =====
  // Daftar produk yang aktif (untuk etalase toko)
  if (p === '/api/products' && method === 'GET') {
    const { results } = await env.DB.prepare(
      'SELECT id, name, description, price, stock, image_url FROM products WHERE active = 1 ORDER BY created_at DESC'
    ).all();
    return json(results);
  }

  // Buat pesanan (publik)
  if (p === '/api/orders' && method === 'POST') {
    const body = await readBody(req);
    const name = (body.customer_name || '').toString().trim();
    const contact = (body.customer_contact || '').toString().trim();
    const items = Array.isArray(body.items) ? body.items : [];
    if (!name || !contact) return error('Nama dan kontak wajib diisi');
    if (items.length === 0) return error('Keranjang kosong');

    let total = 0;
    const lines = [];
    for (const it of items) {
      const pid = Number(it.product_id);
      const qty = Math.max(1, Math.floor(Number(it.qty) || 1));
      const row = await env.DB.prepare(
        'SELECT id, name, price, stock FROM products WHERE id = ? AND active = 1'
      ).bind(pid).first();
      if (!row) return error('Produk tidak ditemukan: ' + pid);
      if (row.stock < qty) return error('Stok tidak cukup untuk: ' + row.name);
      total += row.price * qty;
      lines.push({ product_id: pid, name: row.name, price: row.price, qty });
    }

    await env.DB.prepare(
      'INSERT INTO orders (customer_name, customer_contact, items, total, status, created_at) VALUES (?, ?, ?, ?, ?, ?)'
    ).bind(name, contact, JSON.stringify(lines), total, 'pending', Date.now()).run();

    // Kurangi stok
    for (const l of lines) {
      await env.DB.prepare('UPDATE products SET stock = stock - ? WHERE id = ?').bind(l.qty, l.product_id).run();
    }
    return json({ ok: true, total }, 201);
  }

  // Login admin
  if (p === '/api/admin/login' && method === 'POST') {
    const body = await readBody(req);
    const pw = (body.password || '').toString();
    if (!env.ADMIN_PASSWORD || !timingSafeEqual(pw, env.ADMIN_PASSWORD)) return error('Password salah', 401);
    const token = await signToken(env.ADMIN_SECRET, {
      exp: Date.now() + 1000 * 60 * 60 * 24 * 7, role: 'admin',
    });
    return json({ token });
  }

  // ===== ADMIN (butuh token) =====
  const admin = await getTokenPayload(req, env);
  if (!admin) return error('Unauthorized', 401);

  if (p === '/api/admin/products' && method === 'GET') {
    const { results } = await env.DB.prepare('SELECT * FROM products ORDER BY created_at DESC').all();
    return json(results);
  }
  if (p === '/api/admin/products' && method === 'POST') {
    const b = await readBody(req);
    const name = (b.name || '').toString().trim();
    if (!name) return error('Nama produk wajib');
    const price = Number(b.price) || 0;
    const stock = Math.max(0, Math.floor(Number(b.stock) || 0));
    await env.DB.prepare(
      'INSERT INTO products (name, description, price, stock, image_url, active, created_at) VALUES (?,?,?,?,?,?,?)'
    ).bind(name, (b.description || '').toString(), price, stock, (b.image_url || '').toString(), b.active === false ? 0 : 1, Date.now()).run();
    return json({ ok: true }, 201);
  }

  let m = p.match(/^\/api\/admin\/products\/(\d+)$/);
  if (m && method === 'PUT') {
    const id = Number(m[1]);
    const b = await readBody(req);
    const sets = [], binds = [];
    if (b.name !== undefined) { sets.push('name = ?'); binds.push(b.name.toString()); }
    if (b.description !== undefined) { sets.push('description = ?'); binds.push(b.description.toString()); }
    if (b.price !== undefined) { sets.push('price = ?'); binds.push(Number(b.price)); }
    if (b.stock !== undefined) { sets.push('stock = ?'); binds.push(Math.max(0, Math.floor(Number(b.stock)))); }
    if (b.image_url !== undefined) { sets.push('image_url = ?'); binds.push(b.image_url.toString()); }
    if (b.active !== undefined) { sets.push('active = ?'); binds.push(b.active ? 1 : 0); }
    if (sets.length === 0) return error('Tidak ada field diubah');
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
    await env.DB.prepare('UPDATE orders SET status = ? WHERE id = ?').bind((b.status || 'pending').toString(), Number(m[1])).run();
    return json({ ok: true });
  }

  return error('Not found', 404);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/api/')) return handleApi(request, env, url);
    // Sajikan asset statis (toko & admin) dari folder public/
    return env.ASSETS.fetch(request);
  },
};
