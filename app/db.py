#!/usr/bin/env python3
"""SQLite cho ShopDesk — bảng orders theo hợp đồng API."""
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data")
# Cho phép đổi đường dẫn DB qua biến môi trường (deploy cloud dùng ổ đĩa riêng).
DB_PATH = os.environ.get("SHOPDESK_DB_PATH") or os.path.join(DB_DIR, "shopdesk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop TEXT NOT NULL DEFAULT 'hana',          -- 'hana' | 'bedan'
    customer_name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    items TEXT DEFAULT '[]',                     -- JSON text
    total INTEGER DEFAULT 0,                     -- VND
    status TEXT DEFAULT 'new',                   -- new|pending|shipped|done|cancelled
    shipping_carrier TEXT DEFAULT '',            -- ''|ghn|ghtk|viettelpost|jt
    shipping_code TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    source_thread TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_shop ON orders(shop);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);

-- Lịch sử đẩy đơn sang hãng vận chuyển (thành công hay thất bại đều ghi)
CREATE TABLE IF NOT EXISTS shipment_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL DEFAULT 0,
    carrier TEXT NOT NULL DEFAULT '',
    success INTEGER NOT NULL DEFAULT 0,   -- 1 = thành công, 0 = thất bại
    message TEXT DEFAULT '',               -- mã vận đơn hoặc lý do lỗi (tiếng Việt)
    created_at TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_attempts_order ON shipment_attempts(order_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created ON shipment_attempts(created_at DESC);
"""

VALID_STATUS = {"new", "pending", "shipped", "done", "cancelled"}
VALID_SHOP = {"hana", "bedan", "xinh"}


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now():
    # Giờ Việt Nam (+07) — khớp ngày user chọn khi lọc theo ngày
    vn = timezone(timedelta(hours=7))
    return datetime.now(vn).strftime("%Y-%m-%d %H:%M:%S")


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    # Chuẩn hóa items về JSON text hợp lệ
    try:
        json.loads(d.get("items") or "[]")
    except (json.JSONDecodeError, TypeError):
        d["items"] = "[]"
    return d


def create_order(data):
    data = data or {}
    shop = str(data.get("shop", "hana")).lower()
    if shop not in VALID_SHOP:
        raise ValueError("shop phải là 'hana', 'bedan' hoặc 'xinh'")
    status = str(data.get("status", "new")).lower()
    if status not in VALID_STATUS:
        raise ValueError("status không hợp lệ")
    items = data.get("items", [])
    if not isinstance(items, str):
        items = json.dumps(items, ensure_ascii=False)
    now = _now()
    conn = _connect()
    try:
        cur = conn.execute(
            """INSERT INTO orders
               (shop, customer_name, phone, address, items, total, status,
                shipping_carrier, shipping_code, notes, source_thread, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                shop,
                str(data.get("customer_name", "") or ""),
                str(data.get("phone", "") or ""),
                str(data.get("address", "") or ""),
                items,
                int(data.get("total", 0) or 0),
                status,
                str(data.get("shipping_carrier", "") or ""),
                str(data.get("shipping_code", "") or ""),
                str(data.get("notes", "") or ""),
                str(data.get("source_thread", "") or ""),
                now,
                now,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_order(order_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return row_to_dict(row)
    finally:
        conn.close()


def list_orders(status=None, shop=None, q=None, has_phone=None,
               date_from=None, date_to=None, tag=None, sku=None):
    clauses, params = [], []
    if status:
        clauses.append("o.status = ?")
        params.append(status)
    if shop:
        clauses.append("o.shop = ?")
        params.append(shop)
    if q:
        clauses.append("(o.customer_name LIKE ? OR o.phone LIKE ? OR o.address LIKE ? OR o.shipping_code LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])
    if has_phone is True:
        clauses.append("(o.phone IS NOT NULL AND o.phone != '')")
    elif has_phone is False:
        clauses.append("(o.phone IS NULL OR o.phone = '')")
    if date_from:
        clauses.append("o.created_at >= ?")
        params.append(_date_bound(date_from, start=True))
    if date_to:
        clauses.append("o.created_at <= ?")
        params.append(_date_bound(date_to, start=False))
    if tag:
        if tag == "__none__":
            # Nhóm "Không có tag": không có thread nguồn, hoặc thread chưa gắn tag nào
            clauses.append(
                "(o.source_thread IS NULL OR o.source_thread = '' OR NOT EXISTS "
                "(SELECT 1 FROM conversation_tags ct WHERE o.source_thread LIKE 'fb:%' "
                "AND ct.thread_id = substr(o.source_thread, instr(o.source_thread, '/') + 1)))"
            )
        else:
            clauses.append(
                "EXISTS (SELECT 1 FROM conversation_tags ct WHERE ct.tag = ? "
                "AND o.source_thread LIKE 'fb:%' "
                "AND ct.thread_id = substr(o.source_thread, instr(o.source_thread, '/') + 1))"
            )
            params.append(tag)
    if sku:
        clauses.append("o.items LIKE ?")
        params.append(f"%{sku}%")
    sql = "SELECT o.* FROM orders o"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY o.id DESC"
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()


def _date_bound(s, start=True):
    """'2026-11-01' → '2026-11-01 00:00:00' / '2026-11-01 23:59:59'."""
    s = str(s or "").strip()
    if len(s) == 10:
        return s + (" 00:00:00" if start else " 23:59:59")
    return s


UPDATABLE = {
    "shop", "customer_name", "phone", "address", "items", "total", "status",
    "shipping_carrier", "shipping_code", "notes", "source_thread",
}


def update_order(order_id, patch):
    patch = {k: v for k, v in (patch or {}).items() if k in UPDATABLE}
    if not patch:
        return False
    if "shop" in patch and str(patch["shop"]).lower() not in VALID_SHOP:
        raise ValueError("shop phải là 'hana', 'bedan' hoặc 'xinh'")
    if "status" in patch and str(patch["status"]).lower() not in VALID_STATUS:
        raise ValueError("status không hợp lệ")
    if "items" in patch and not isinstance(patch["items"], str):
        patch["items"] = json.dumps(patch["items"], ensure_ascii=False)
    if "total" in patch:
        patch["total"] = int(patch["total"] or 0)
    patch["updated_at"] = _now()
    sets = ", ".join(f"{k} = ?" for k in patch)
    conn = _connect()
    try:
        cur = conn.execute(f"UPDATE orders SET {sets} WHERE id = ?", (*patch.values(), order_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_order(order_id):
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ---- Lịch sử đẩy đơn sang hãng vận chuyển ----

def log_shipment_attempt(order_id, carrier, success, message):
    """Ghi 1 dòng lịch sử mỗi lần đẩy đơn (thành công hay thất bại đều ghi)."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO shipment_attempts (order_id, carrier, success, message, created_at)"
            " VALUES (?,?,?,?,?)",
            (int(order_id or 0), str(carrier or ""), 1 if success else 0,
             str(message or ""), _now()),
        )
        conn.commit()
    finally:
        conn.close()


def list_shipment_attempts(order_id=None, limit=100):
    """Lịch sử đẩy đơn, mới nhất trước. Lọc theo order_id nếu có."""
    try:
        limit = max(1, min(500, int(limit or 100)))
    except (TypeError, ValueError):
        limit = 100
    sql = "SELECT * FROM shipment_attempts"
    params = []
    if order_id:
        sql += " WHERE order_id = ?"
        params.append(int(order_id))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
