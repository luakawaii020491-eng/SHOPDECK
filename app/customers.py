#!/usr/bin/env python3
"""Routes /api/customers* — quản lý khách hàng, dedupe theo SĐT."""
import re
import sqlite3

from flask import Blueprint, jsonify, request

from . import db as db_mod

customers_bp = Blueprint("customers", __name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT '',
    shop TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT '',
    updated_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone) WHERE phone != '';
"""


def init_customers():
    conn = db_mod._connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


def normalize_phone(phone):
    """Chuẩn hóa SĐT: bỏ khoảng trắng, dấu chấm, dấu gạch."""
    return re.sub(r"[\s.\-]", "", str(phone or "")).strip()


def _row_dict(row):
    return dict(row) if row is not None else None


def get_customer(customer_id):
    conn = db_mod._connect()
    try:
        row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return _row_dict(row)
    finally:
        conn.close()


def get_by_phone(phone):
    phone = normalize_phone(phone)
    if not phone:
        return None
    conn = db_mod._connect()
    try:
        row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
        return _row_dict(row)
    finally:
        conn.close()


def upsert_customer(phone, name="", address="", shop="", notes=""):
    """Tạo mới hoặc cập nhật khách hàng theo SĐT (dạng chuẩn hóa).

    Giá trị mới khác rỗng sẽ ghi đè, giá trị rỗng giữ nguyên dữ liệu cũ.
    Trả về id của khách hàng; phone trống → trả None, không làm gì.
    """
    phone = normalize_phone(phone)
    if not phone:
        return None
    name = str(name or "").strip()
    address = str(address or "").strip()
    shop = str(shop or "").strip().lower()
    notes = str(notes or "").strip()
    now = db_mod._now()
    conn = db_mod._connect()
    try:
        row = conn.execute("SELECT id FROM customers WHERE phone = ?", (phone,)).fetchone()
        if row:
            conn.execute(
                """UPDATE customers SET
                       name = COALESCE(NULLIF(?, ''), name),
                       address = COALESCE(NULLIF(?, ''), address),
                       shop = COALESCE(NULLIF(?, ''), shop),
                       notes = COALESCE(NULLIF(?, ''), notes),
                       updated_at = ?
                   WHERE id = ?""",
                (name, address, shop, notes, now, row["id"]),
            )
            conn.commit()
            return row["id"]
        cur = conn.execute(
            """INSERT INTO customers (name, phone, address, shop, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (name, phone, address, shop, notes, now, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@customers_bp.get("/api/customers")
def list_customers():
    q = (request.args.get("q") or "").strip()
    conn = db_mod._connect()
    try:
        if q:
            like = f"%{q}%"
            rows = conn.execute(
                "SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY id DESC",
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
        return jsonify({"customers": [_row_dict(r) for r in rows]})
    finally:
        conn.close()


@customers_bp.post("/api/customers")
def create_customer():
    body = request.get_json(silent=True) or {}
    phone = normalize_phone(body.get("phone"))
    kwargs = {
        "name": body.get("name"),
        "address": body.get("address"),
        "shop": body.get("shop"),
        "notes": body.get("notes"),
    }
    if phone:
        # SĐT đã tồn tại → cập nhật thông tin mới nhất; chưa có → tạo mới
        existing = get_by_phone(phone)
        try:
            cid = upsert_customer(phone, **kwargs)
        except Exception:
            return _err("Không lưu được khách hàng. Kiểm tra lại dữ liệu.", 500)
        return jsonify({"ok": True, "id": cid, "updated": existing is not None})
    # SĐT trống → vẫn cho tạo, không dedupe
    now = db_mod._now()
    conn = db_mod._connect()
    try:
        cur = conn.execute(
            """INSERT INTO customers (name, phone, address, shop, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                str(body.get("name") or "").strip(),
                "",
                str(body.get("address") or "").strip(),
                str(body.get("shop") or "").strip().lower(),
                str(body.get("notes") or "").strip(),
                now,
                now,
            ),
        )
        conn.commit()
        cid = cur.lastrowid
    except Exception:
        return _err("Không lưu được khách hàng. Kiểm tra lại dữ liệu.", 500)
    finally:
        conn.close()
    return jsonify({"ok": True, "id": cid, "updated": False})


@customers_bp.get("/api/customers/<int:customer_id>")
def detail_customer(customer_id):
    c = get_customer(customer_id)
    if c is None:
        return _err("Không tìm thấy khách hàng.", 404)
    return jsonify({"ok": True, "customer": c})


@customers_bp.put("/api/customers/<int:customer_id>")
def update_customer(customer_id):
    if get_customer(customer_id) is None:
        return _err("Không tìm thấy khách hàng.", 404)
    body = request.get_json(silent=True) or {}
    patch = {}
    for k in ("name", "address", "notes"):
        if k in body:
            patch[k] = str(body.get(k) or "").strip()
    if "shop" in body:
        patch["shop"] = str(body.get("shop") or "").strip().lower()
    if "phone" in body:
        patch["phone"] = normalize_phone(body.get("phone"))
    if not patch:
        return _err("Không có thông tin nào để cập nhật.")
    patch["updated_at"] = db_mod._now()
    sets = ", ".join(f"{k} = ?" for k in patch)
    conn = db_mod._connect()
    try:
        try:
            conn.execute(
                f"UPDATE customers SET {sets} WHERE id = ?",
                (*patch.values(), customer_id),
            )
        except sqlite3.IntegrityError:
            return _err("SĐT này đã thuộc về khách hàng khác.", 409)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@customers_bp.delete("/api/customers/<int:customer_id>")
def delete_customer(customer_id):
    conn = db_mod._connect()
    try:
        cur = conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
        conn.commit()
        if cur.rowcount == 0:
            return _err("Không tìm thấy khách hàng.", 404)
    finally:
        conn.close()
    return jsonify({"ok": True})


@customers_bp.get("/api/customers/by-phone")
def by_phone():
    phone = request.args.get("phone") or ""
    if not normalize_phone(phone):
        return _err("Thiếu SĐT để tra cứu.")
    return jsonify({"customer": get_by_phone(phone)})
