#!/usr/bin/env python3
"""Quản lý sản phẩm theo mã SKU (Dép Hana, Bé Đan & Dép Xinh).

- Bảng `products`: sku duy nhất, giá theo đôi, stock NULL = không giới hạn.
- `init_products()` tạo bảng (idempotent) + seed 42 SKU khi bảng còn trống.
- Blueprint `products_bp`: CRUD qua /api/products*.
- Helpers cho chốt đơn nhanh: get_by_sku(), resolve_items(), decrement_stock().
"""
import sqlite3

from flask import Blueprint, jsonify, request

from . import db as db_mod

products_bp = Blueprint("products", __name__)

VALID_SHOP = {"hana", "bedan", "xinh"}
SHOP_VI = {"hana": "Dép Hana", "bedan": "Bé Đan", "xinh": "Dép Xinh"}

SCHEMA_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    shop TEXT DEFAULT 'hana',
    color TEXT DEFAULT '',
    size TEXT DEFAULT '',
    price INTEGER DEFAULT 0,
    stock INTEGER NULL,
    image TEXT DEFAULT '',
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
"""

CREATABLE = {"sku", "name", "shop", "color", "size", "price", "stock", "image", "note"}
UPDATABLE = {"sku", "name", "shop", "color", "size", "price", "stock", "image", "note"}


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


def _validate(data):
    """Kiểm tra trường chung cho tạo/sửa. Trả về chuỗi lỗi tiếng Việt hoặc None."""
    sku = str(data.get("sku") or "").strip()
    if not sku:
        return "Vui lòng nhập mã SKU."
    shop = str(data.get("shop") or "hana").lower()
    if shop not in VALID_SHOP:
        return "Shop phải là 'hana', 'bedan' hoặc 'xinh'."
    try:
        price = int(data.get("price") or 0)
    except (TypeError, ValueError):
        return "Giá bán không hợp lệ."
    if price < 0:
        return "Giá bán không được nhỏ hơn 0."
    stock = data.get("stock")
    if stock not in (None, ""):
        try:
            stock = int(stock)
        except (TypeError, ValueError):
            return "Tồn kho không hợp lệ."
        if stock < 0:
            return "Tồn kho không được nhỏ hơn 0."
    return None


def _seed_rows():
    """42 SKU mặc định: 15 Hana (dép sục khoét lỗ, 65k) + 15 Bé Đan
    (dép sục đế 3 phân, 49k) + 12 Dép Xinh (dép nữ quai ngang, 49k)."""
    rows = []
    colors = [("DEN", "Đen"), ("NAU", "Nâu"), ("KEM", "Kem")]
    for code, vi in colors:
        for size in range(36, 41):
            rows.append({
                "sku": f"HANA-SUC-{code}-{size}",
                "name": "Dép sục khoét lỗ",
                "shop": "hana",
                "color": vi,
                "size": str(size),
                "price": 65000,
                "stock": None,
                "image": f"dep_suc_{'den' if code == 'DEN' else 'nau' if code == 'NAU' else 'kem'}.jpg",
                "note": "",
            })
    for code, vi in colors:
        for size in range(36, 41):
            rows.append({
                "sku": f"BEDAN-3P-{code}-{size}",
                "name": "Dép sục đế 3 phân",
                "shop": "bedan",
                "color": vi,
                "size": str(size),
                "price": 49000,
                "stock": None,
                "image": "dep_suc_3phan_all.jpg",
                "note": "",
            })
    # Dép Xinh — dép nữ quai ngang siêu êm, 49k/đôi, size 36–39
    # Giá COD làm tròn (chủ shop 2026-11-01): 1 đôi 80k, 2 đôi 100k, 3 đôi 150k
    for code, vi in colors:
        for size in range(36, 40):
            rows.append({
                "sku": f"XINH-QN-{code}-{size}",
                "name": "Dép nữ quai ngang siêu êm",
                "shop": "xinh",
                "color": vi,
                "size": str(size),
                "price": 49000,
                "stock": None,
                "image": "dep_xinh_quai_ngang.jpg",
                "note": "",
            })
    return rows


def init_products():
    """Tạo bảng + index (idempotent). Seed 42 SKU mặc định chỉ khi bảng còn trống."""
    conn = db_mod._connect()
    try:
        conn.executescript(SCHEMA_PRODUCTS)
        count = conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
        if count == 0:
            now = db_mod._now()
            for r in _seed_rows():
                conn.execute(
                    """INSERT INTO products
                       (sku, name, shop, color, size, price, stock, image, note, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["sku"], r["name"], r["shop"], r["color"], r["size"], r["price"],
                     r["stock"], r["image"], r["note"], now, now),
                )
        conn.commit()
    finally:
        conn.close()


def _norm(data, fields):
    """Chuẩn hóa dữ liệu đầu vào về đúng kiểu cột."""
    out = {}
    for k in fields:
        v = data.get(k)
        if k == "price":
            out[k] = int(v or 0)
        elif k == "stock":
            out[k] = None if v in (None, "") else int(v)
        elif k == "shop":
            out[k] = str(v or "hana").lower()
        else:
            out[k] = str(v if v is not None else "")
    return out


def _row_dict(row):
    return dict(row) if row is not None else None


# ---------------- Helpers dùng cho chốt đơn nhanh ----------------

def get_by_sku(sku):
    """Tìm sản phẩm theo SKU (không phân biệt hoa/thường). Trả dict hoặc None."""
    conn = db_mod._connect()
    try:
        row = conn.execute(
            "SELECT * FROM products WHERE UPPER(sku) = UPPER(?)", (str(sku or "").strip(),)
        ).fetchone()
        return _row_dict(row)
    finally:
        conn.close()


def resolve_items(items):
    """items = [{sku, qty}] → (lines, subtotal).
    lines = [{sku, name, price, qty, line_total}]. Raise ValueError tiếng Việt khi lỗi."""
    lines = []
    subtotal = 0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        sku = str(it.get("sku") or "").strip()
        try:
            qty = int(it.get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0
        prod = get_by_sku(sku) if sku else None
        if prod is None:
            raise ValueError(f"Không tìm thấy sản phẩm mã {sku or '?'}.")
        if qty <= 0:
            raise ValueError(f"Số lượng của mã {sku} phải lớn hơn 0.")
        stock = prod.get("stock")
        if stock is not None and stock < qty:
            raise ValueError(f"Tồn kho mã {sku} chỉ còn {stock}.")
        price = int(prod.get("price") or 0)
        line_total = price * qty
        lines.append({
            "sku": prod["sku"],
            "name": prod.get("name") or "",
            "price": price,
            "qty": qty,
            "line_total": line_total,
        })
        subtotal += line_total
    return lines, subtotal


def decrement_stock(sku, qty):
    """Trừ tồn kho sau khi chốt đơn. Bỏ qua khi stock IS NULL (không giới hạn)."""
    conn = db_mod._connect()
    try:
        row = conn.execute(
            "SELECT id, stock FROM products WHERE UPPER(sku) = UPPER(?)",
            (str(sku or "").strip(),),
        ).fetchone()
        if row is None:
            raise ValueError(f"Không tìm thấy sản phẩm mã {sku}.")
        stock = row["stock"]
        if stock is None:
            return True
        qty = int(qty or 0)
        if stock < qty:
            raise ValueError(f"Tồn kho mã {sku} chỉ còn {stock}.")
        conn.execute(
            "UPDATE products SET stock = stock - ?, updated_at = ? WHERE id = ?",
            (qty, db_mod._now(), row["id"]),
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ---------------- API ----------------

@products_bp.get("/api/products")
def list_products():
    q = (request.args.get("q") or "").strip()
    shop = (request.args.get("shop") or "").strip().lower()
    clauses, params = [], []
    if shop:
        clauses.append("shop = ?")
        params.append(shop)
    if q:
        clauses.append("(sku LIKE ? OR name LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    sql = "SELECT * FROM products"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    conn = db_mod._connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return jsonify({"products": [dict(r) for r in rows]})
    finally:
        conn.close()


@products_bp.post("/api/products")
def create_product():
    body = request.get_json(silent=True) or {}
    err = _validate(body)
    if err:
        return _err(err)
    data = _norm(body, CREATABLE)
    now = db_mod._now()
    conn = db_mod._connect()
    try:
        cur = conn.execute(
            """INSERT INTO products
               (sku, name, shop, color, size, price, stock, image, note, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (data["sku"].strip(), data["name"], data["shop"], data["color"], data["size"],
             data["price"], data["stock"], data["image"], data["note"], now, now),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})
    except sqlite3.IntegrityError:
        return _err("Mã SKU đã tồn tại.", 400)
    finally:
        conn.close()


@products_bp.get("/api/products/<int:product_id>")
def get_product(product_id):
    conn = db_mod._connect()
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    finally:
        conn.close()
    prod = _row_dict(row)
    if prod is None:
        return _err("Không tìm thấy sản phẩm.", 404)
    return jsonify({"ok": True, "product": prod})


@products_bp.put("/api/products/<int:product_id>")
def update_product(product_id):
    body = request.get_json(silent=True) or {}
    patch = {k: v for k, v in body.items() if k in UPDATABLE}
    if not patch:
        return _err("Không có dữ liệu nào để cập nhật.")
    # Ghép với dữ liệu hiện tại để validate đầy đủ
    conn = db_mod._connect()
    try:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return _err("Không tìm thấy sản phẩm.", 404)
    merged = dict(row)
    merged.update(patch)
    err = _validate(merged)
    if err:
        return _err(err)
    data = _norm(merged, UPDATABLE)
    data["updated_at"] = db_mod._now()
    sets = ", ".join(f"{k} = ?" for k in data)
    conn = db_mod._connect()
    try:
        cur = conn.execute(
            f"UPDATE products SET {sets} WHERE id = ?", (*data.values(), product_id)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return _err("Mã SKU đã tồn tại.", 400)
    finally:
        conn.close()
    if cur.rowcount == 0:
        return _err("Không tìm thấy sản phẩm.", 404)
    return jsonify({"ok": True})


@products_bp.delete("/api/products/<int:product_id>")
def delete_product(product_id):
    conn = db_mod._connect()
    try:
        cur = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        if cur.rowcount == 0:
            return _err("Không tìm thấy sản phẩm.", 404)
    finally:
        conn.close()
    return jsonify({"ok": True})
