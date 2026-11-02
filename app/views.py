#!/usr/bin/env python3
"""Routes trang HTML: / (inbox), /orders, /settings, /lendon (tạo đơn kiểu Sapo),
/print/label/<id> (in tem theo mẫu hãng vận chuyển)."""
import json

from flask import Blueprint, render_template, request

from . import db as db_mod
from . import config as config_mod

views_bp = Blueprint("views", __name__)

CARRIER_INFO = {
    "ghn": {"name": "Giao Hàng Nhanh (GHN)", "short": "GHN"},
    "ghtk": {"name": "Giao Hàng Tiết Kiệm", "short": "GHTK"},
    "viettelpost": {"name": "Viettel Post", "short": "VTP"},
    "jt": {"name": "J&T Express", "short": "J&T"},
    "best": {"name": "Best Express", "short": "BEST"},
}

SHOP_VI = {"hana": "Dép Hana", "bedan": "Shop Bé Đan", "xinh": "Dép Xinh"}


@views_bp.get("/")
def inbox():
    return render_template("inbox.html")


@views_bp.get("/orders")
def orders():
    return render_template("orders.html")


@views_bp.get("/products")
def products():
    return render_template("products.html")


@views_bp.get("/customers")
def customers():
    return render_template("customers.html")


@views_bp.get("/settings")
def settings():
    return render_template("settings.html")


@views_bp.get("/lendon")
def lendon():
    """Trang lên đơn nhanh — giao diện giống màn hình tạo đơn của Sapo:
    thông tin khách hàng + sản phẩm (trái), thanh toán + vận chuyển (phải)."""
    return render_template("lendon.html")


@views_bp.get("/print/label/<int:order_id>")
def print_label(order_id):
    """Trang in tem/phiếu giao hàng theo mẫu từng hãng vận chuyển (khổ 100x150mm).
    ?carrier=ghn|ghtk|viettelpost|jt|best — mặc định dùng hãng đã lưu của đơn."""
    order = db_mod.get_order(order_id)
    if not order:
        return {"ok": False, "error_vi": "Không tìm thấy đơn hàng."}, 404
    carrier = (request.args.get("carrier") or order.get("shipping_carrier") or "ghn").lower()
    if carrier not in CARRIER_INFO:
        carrier = "ghn"
    sender = config_mod.get_sender()
    label = {
        "order_id": order.get("id"),
        "shop": SHOP_VI.get(order.get("shop"), order.get("shop") or ""),
        "customer_name": order.get("customer_name") or "",
        "phone": order.get("phone") or "",
        "address": order.get("address") or "",
        "items": order.get("items") or "[]",
        "total": int(order.get("total") or 0),
        "notes": order.get("notes") or "",
        "carrier": carrier,
        "carrier_name": CARRIER_INFO[carrier]["name"],
        "carrier_short": CARRIER_INFO[carrier]["short"],
        "shipping_code": order.get("shipping_code") or f"SD#{order.get('id'):06d}",
        "created_at": order.get("created_at") or "",
        "sender_name": sender.get("shop_name") or SHOP_VI.get(order.get("shop"), "Shop"),
        "sender_phone": sender.get("sender_phone") or "",
        "sender_address": sender.get("sender_address") or "",
    }
    return render_template(
        "label.html",
        label_json=json.dumps(label, ensure_ascii=False),
        carrier=carrier,
        autoprint=(request.args.get("print") == "1"),
    )
