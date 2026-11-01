#!/usr/bin/env python3
"""Routes /api/orders*, /api/orders/quick và /api/price_suggest."""
import csv
import io
import json

from flask import Blueprint, Response, jsonify, request

from . import db as db_mod
from . import customers as customers_mod
from . import products as products_mod
from . import tags as tags_mod

orders_bp = Blueprint("orders", __name__)

SHOP_VI = {"hana": "Dép Hana", "bedan": "Bé Đan", "xinh": "Dép Xinh"}
STATUS_VI = {
    "new": "Mới",
    "pending": "Chờ xử lý",
    "shipped": "Đã gửi hàng",
    "done": "Hoàn tất",
    "cancelled": "Đã hủy",
}
CARRIER_VI = {"ghn": "GHN", "ghtk": "GHTK", "viettelpost": "Viettel Post", "jt": "J&T", "best": "Best Express"}


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


@orders_bp.get("/api/orders")
def list_orders():
    has_phone = request.args.get("has_phone")
    if has_phone == "true":
        has_phone = True
    elif has_phone == "false":
        has_phone = False
    else:
        has_phone = None
    orders = db_mod.list_orders(
        status=request.args.get("status") or None,
        shop=request.args.get("shop") or None,
        q=request.args.get("q") or None,
        has_phone=has_phone,
        date_from=request.args.get("date_from") or None,
        date_to=request.args.get("date_to") or None,
        tag=request.args.get("tag") or None,
        sku=request.args.get("sku") or None,
    )
    return jsonify({"orders": orders})


@orders_bp.post("/api/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    try:
        order_id = db_mod.create_order(body)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err("Không tạo được đơn hàng. Kiểm tra lại dữ liệu.", 500)
    # Upsert khách hàng theo SĐT + auto-tag khi đơn tạo từ thread inbox
    try:
        customers_mod.upsert_customer(
            body.get("phone"), body.get("customer_name"),
            body.get("address"), body.get("shop"), body.get("notes"))
    except Exception:
        pass
    try:
        tags_mod.auto_tag_order_created(body.get("source_thread") or "")
    except Exception:
        pass
    return jsonify({"ok": True, "id": order_id})


@orders_bp.get("/api/orders/<int:order_id>")
def get_order(order_id):
    o = db_mod.get_order(order_id)
    if not o:
        return _err("Không tìm thấy đơn hàng.", 404)
    return jsonify({"order": o})


@orders_bp.put("/api/orders/<int:order_id>")
def update_order(order_id):
    body = request.get_json(silent=True) or {}
    try:
        updated = db_mod.update_order(order_id, body)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err("Không cập nhật được đơn hàng.", 500)
    if not updated:
        return _err("Không tìm thấy đơn hàng.", 404)
    return jsonify({"ok": True})


@orders_bp.delete("/api/orders/<int:order_id>")
def delete_order(order_id):
    if not db_mod.delete_order(order_id):
        return _err("Không tìm thấy đơn hàng.", 404)
    return jsonify({"ok": True})


def _items_text(items_json):
    try:
        items = json.loads(items_json or "[]")
    except (ValueError, TypeError):
        return ""
    if isinstance(items, dict):
        items = [items]
    parts = []
    for it in items:
        if not isinstance(it, dict):
            continue
        qty = it.get("qty") or it.get("quantity") or 1
        desc = " ".join(str(it.get(k) or "") for k in ("color", "size", "name")).strip()
        parts.append(f"{qty}x {desc}".strip() if desc else f"{qty}x")
    return "; ".join(parts)


@orders_bp.get("/api/orders/export.csv")
def export_csv():
    orders = db_mod.list_orders()
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM để Excel mở đúng tiếng Việt
    writer = csv.writer(buf)
    writer.writerow(["ID", "Shop", "Ngày tạo", "Khách hàng", "SĐT", "Địa chỉ",
                     "Mặt hàng", "Tổng tiền", "Trạng thái", "Hãng VC", "Mã vận đơn", "Ghi chú"])
    for o in orders:
        writer.writerow([
            o.get("id"), SHOP_VI.get(o.get("shop"), o.get("shop")),
            o.get("created_at"), o.get("customer_name"), o.get("phone"), o.get("address"),
            _items_text(o.get("items")), o.get("total"),
            STATUS_VI.get(o.get("status"), o.get("status")),
            CARRIER_VI.get(o.get("shipping_carrier"), o.get("shipping_carrier")),
            o.get("shipping_code"), o.get("notes"),
        ])
    return Response(
        buf.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=don_hang_shopdesk.csv"},
    )


# ---- Bảng giá gợi ý ----
# hana: 1 đôi = 90000 (65k+25k ship); >=2 đôi = 65000*N miễn ship
# bedan: 1 đôi = 79000 (49k+30k ship); 2 đôi = 99000 miễn ship; >=3 đôi = 139000 miễn ship
# xinh: COD làm tròn theo yêu cầu chủ shop (2026-11-01):
#   1 đôi = 80000 (49k+30k ship=79k, làm tròn); 2 đôi = 100000 (99k, làm tròn);
#   3 đôi = 150000 miễn ship; >3 đôi = 150k + 50k/đôi thêm, miễn ship

def _suggest(shop, qty):
    if shop == "hana":
        if qty <= 0:
            return None, "Số lượng phải lớn hơn 0."
        if qty == 1:
            return 90000, "1 đôi: 65k tiền dép + 25k ship."
        return 65000 * qty, f"{qty} đôi: 65k × {qty}, miễn ship."
    if shop == "bedan":
        if qty <= 0:
            return None, "Số lượng phải lớn hơn 0."
        if qty == 1:
            return 79000, "1 đôi: 49k tiền dép + 30k ship."
        if qty == 2:
            return 99000, "2 đôi: 99k, miễn ship."
        return 139000, f"{qty} đôi: 139k, miễn ship."
    if shop == "xinh":
        if qty <= 0:
            return None, "Số lượng phải lớn hơn 0."
        if qty == 1:
            return 80000, "1 đôi: 49k + 30k ship = 79k, COD làm tròn 80k."
        if qty == 2:
            return 100000, "2 đôi: 99k miễn ship, COD làm tròn 100k."
        if qty == 3:
            return 150000, "3 đôi: 150k miễn ship."
        extra = qty - 3
        return 150000 + 50000 * extra, f"{qty} đôi: 150k + 50k × {extra} đôi thêm, miễn ship."
    return None, "shop phải là 'hana', 'bedan' hoặc 'xinh'."


@orders_bp.get("/api/price_suggest")
def price_suggest():
    shop = (request.args.get("shop") or "").lower()
    try:
        qty = int(request.args.get("qty") or 0)
    except (TypeError, ValueError):
        qty = 0
    total, note = _suggest(shop, qty)
    if total is None:
        return jsonify({"ok": False, "error_vi": note})
    return jsonify({"ok": True, "total": total, "note": note})


# ---- Chốt đơn nhanh từ SKU ("chốt đơn và lên đơn luôn") ----
# POST /api/orders/quick
# body: {shop, customer_name, phone, address, items: [{sku, qty}],
#        notes, source_thread, create_shipment: {carrier} | null}
# Tổng = Σ(giá SKU × số lượng) + ship (hana: 1 đôi +25k, ≥2 đôi free;
#        bedan: 1 đôi +30k, ≥2 đôi free; xinh: 1 đôi +30k, ≥2 đôi free).
# Lưu ý: Bé Đan 2 đôi theo công thức này = 98k (2×49k), trong khi giá bán
# lẻ cho khách là 99k — nhân viên kiểm tra lại tổng trước khi xác nhận.
# Dép Xinh: tổng đơn = COD làm tròn (chủ shop 2026-11-01): 1 đôi 80k,
# 2 đôi 100k, 3 đôi 150k — ghi đè công thức Σ giá SKU + ship.

def _quick_ship_fee(shop, total_qty):
    if shop == "hana":
        return 25000 if total_qty == 1 else 0
    if shop == "xinh":
        return 30000 if total_qty == 1 else 0
    return 30000 if total_qty == 1 else 0


@orders_bp.post("/api/orders/quick")
def quick_order():
    # Import tại đây để tránh import vòng (shipping không import orders)
    from . import shipping as shipping_mod

    body = request.get_json(silent=True) or {}
    shop = str(body.get("shop") or "hana").lower()
    if shop not in db_mod.VALID_SHOP:
        return _err("shop phải là 'hana', 'bedan' hoặc 'xinh'.")
    items_in = body.get("items") or []
    if not isinstance(items_in, list) or not items_in:
        return _err("Chưa chọn sản phẩm nào (items trống).")
    phone = str(body.get("phone") or "").strip()
    address = str(body.get("address") or "").strip()
    if not phone:
        return _err("Thiếu số điện thoại khách hàng.")
    if not address:
        return _err("Thiếu địa chỉ khách hàng.")

    # 1. Tính tiền theo SKU
    try:
        lines, subtotal = products_mod.resolve_items(items_in)
    except ValueError as e:
        return _err(str(e))
    total_qty = sum(l["qty"] for l in lines)
    # Tổng trọng lượng theo SKU (gram). SKU chưa nhập trọng lượng tính là 0 —
    # nếu mọi SKU đều chưa có, total_weight_grams = 0 và hãng VC sẽ dùng mặc định.
    total_weight_grams = sum(
        (int(l.get("weight_grams") or 0) * l["qty"]) for l in lines)
    total = subtotal + _quick_ship_fee(shop, total_qty)
    if shop == "xinh":
        # Dép Xinh: tổng đơn = COD làm tròn (1 đôi 80k, 2 đôi 100k, 3 đôi 150k)
        cod, _note = _suggest(shop, total_qty)
        if cod:
            total = cod

    # 2. Trừ tồn kho (resolve đã kiểm tra đủ hàng)
    try:
        for l in lines:
            products_mod.decrement_stock(l["sku"], l["qty"])
    except ValueError as e:
        return _err(str(e))

    # 3. Upsert khách hàng theo SĐT
    try:
        customers_mod.upsert_customer(
            phone, body.get("customer_name"), address, shop, body.get("notes"))
    except Exception:
        pass

    # 4. Tạo đơn
    order_items = [
        {"sku": l["sku"], "name": f"{l['name']} ({l['sku']})",
         "price": l["price"], "qty": l["qty"]}
        for l in lines
    ]
    try:
        order_id = db_mod.create_order({
            "shop": shop,
            "customer_name": str(body.get("customer_name") or ""),
            "phone": phone,
            "address": address,
            "items": order_items,
            "total": total,
            "status": "new",
            "notes": str(body.get("notes") or ""),
            "source_thread": str(body.get("source_thread") or ""),
        })
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err("Không tạo được đơn hàng. Kiểm tra lại dữ liệu.", 500)

    # 5. Auto-tag "Chốt đơn" khi đơn tạo từ thread inbox
    try:
        tags_mod.auto_tag_order_created(body.get("source_thread") or "")
    except Exception:
        pass

    # 6. "Lên đơn luôn": tạo vận đơn ngay nếu có yêu cầu
    shipping_code = None
    shipment_error_vi = None
    cs = body.get("create_shipment")
    if isinstance(cs, dict) and cs.get("carrier"):
        try:
            shipping_code = shipping_mod.create_shipment_for_order(
                order_id, str(cs["carrier"]).lower(),
                weight_grams=total_weight_grams or None)
        except ValueError as e:
            shipment_error_vi = str(e)
        except Exception as e:
            shipment_error_vi = f"Lỗi không xác định: {e.__class__.__name__}"

    return jsonify({
        "ok": True,
        "order_id": order_id,
        "total": total,
        "total_weight_grams": total_weight_grams,
        "shipping_code": shipping_code,
        "shipment_error_vi": shipment_error_vi,
    })
