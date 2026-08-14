-- Migrasi v2: fitur baru (aman dijalankan di DB yang sudah ada)

-- Tambah kolom di products
ALTER TABLE products ADD COLUMN category TEXT DEFAULT 'Lainnya';
ALTER TABLE products ADD COLUMN weight INTEGER DEFAULT 500;          -- gram, untuk hitung ongkir
ALTER TABLE products ADD COLUMN sku TEXT DEFAULT '';

-- orders: alamat, ongkir, metode bayar, resi, kode tracking
ALTER TABLE orders ADD COLUMN address TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN city TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN postal_code TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN shipping_cost REAL DEFAULT 0;
ALTER TABLE orders ADD COLUMN shipping_service TEXT DEFAULT '';
ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'qris';   -- qris | transfer | cod
ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'unpaid'; -- unpaid | paid
ALTER TABLE orders ADD COLUMN tracking_code TEXT DEFAULT '';        -- no resi
ALTER TABLE orders ADD COLUMN tracking_url TEXT DEFAULT '';         -- url lacak (opsional)
ALTER TABLE orders ADD COLUMN notes TEXT DEFAULT '';

-- Tabel settings toko (ongkir manual/flat, kontak WA, QRIS, payment gateway)
CREATE TABLE IF NOT EXISTS settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  store_name TEXT DEFAULT 'TokoKita',
  wa_number TEXT DEFAULT '',                 -- 62812xxxx (tanpa +)
  qris_image_url TEXT DEFAULT '',            -- URL gambar QRIS
  shipping_mode TEXT DEFAULT 'flat',         -- flat | rajaongkir | biteship
  flat_shipping REAL DEFAULT 10000,         -- ongkir flat default
  free_shipping_min REAL DEFAULT 0,         -- gratis ongkir jika total >= nilai ini (0=off)
  rajaongkir_api_key TEXT DEFAULT '',
  rajaongkir_origin INTEGER DEFAULT 0,       -- kode kota asal
  biteship_api_key TEXT DEFAULT '',
  payment_gateway TEXT DEFAULT 'manual',     -- manual | midtrans | xendit
  midtrans_server_key TEXT DEFAULT '',
  midtrans_client_key TEXT DEFAULT '',
  xendit_secret_key TEXT DEFAULT '',
  xendit_public_key TEXT DEFAULT ''
);
INSERT OR IGNORE INTO settings (id) VALUES (1);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
