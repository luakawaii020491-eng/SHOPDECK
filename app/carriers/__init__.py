#!/usr/bin/env python3
"""Các module tích hợp hãng vận chuyển cho ShopDesk.

Mỗi module định nghĩa:
- class CarrierError(Exception): lỗi nghiệp vụ, message đã là tiếng Việt
- create_shipment(order: dict, creds: dict) -> str: tạo đơn, trả mã vận đơn
- track(code: str, creds: dict) -> dict: {status_vi, history: [{time, desc}]}
- test_connection(creds: dict) -> str: kiểm tra key, trả message tiếng Việt

Quy ước chung:
- order: dict đơn hàng từ DB (id, customer_name, phone, address, items (JSON text), total...)
- creds: dict lấy từ config.json (KHÔNG bao giờ log)
- timeout 30s, dùng requests (tự đọc proxy từ environ)
"""
import json


class CarrierError(Exception):
    """Lỗi hãng vận chuyển — message luôn là tiếng Việt, hiển thị trực tiếp cho user."""


CARRIER_NAMES = {
    "ghn": "GHN (Giao Hàng Nhanh)",
    "ghtk": "GHTK (Giao Hàng Tiết Kiệm)",
    "viettelpost": "Viettel Post",
    "jt": "J&T Express",
    "best": "Best Express",
}

CARRIERS = ["ghn", "ghtk", "viettelpost", "jt", "best"]


def items_summary(order):
    """Tóm tắt mặt hàng từ items JSON: '2x Đen size 37; 1x Kem size 38'."""
    try:
        items = json.loads(order.get("items") or "[]")
    except (ValueError, TypeError):
        items = []
    if isinstance(items, dict):
        items = [items]
    parts = []
    total_qty = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        qty = int(it.get("qty") or it.get("quantity") or 1)
        total_qty += qty
        desc = " ".join(str(it.get(k) or "") for k in ("color", "size", "name", "product")).strip()
        parts.append(f"{qty}x {desc}".strip() if desc else f"{qty}x dép")
    if not parts:
        return "Dép sục", 1
    return "; ".join(parts), total_qty or 1
