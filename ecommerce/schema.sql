-- Schema database D1 untuk toko e-commerce
CREATE TABLE IF NOT EXISTS products (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT    NOT NULL,
  description   TEXT    DEFAULT '',
  price         REAL    NOT NULL DEFAULT 0,
  stock         INTEGER NOT NULL DEFAULT 0,
  image_url     TEXT    DEFAULT '',
  active        INTEGER NOT NULL DEFAULT 1,   -- 1=ditampilkan ke publik, 0=disembunyikan
  created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_name   TEXT    NOT NULL,
  customer_contact TEXT   NOT NULL,
  items           TEXT    NOT NULL,            -- JSON array: [{product_id,name,price,qty}]
  total           REAL    NOT NULL DEFAULT 0,
  status          TEXT    NOT NULL DEFAULT 'pending',  -- pending | paid | shipped | done | cancelled
  created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
