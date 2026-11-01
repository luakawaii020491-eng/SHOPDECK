#!/usr/bin/env python3
"""Tích hợp J&T Express.

🔴 CHƯA KIỂM CHỨNG — J&T Open Platform chỉ công bố endpoint chi tiết SAU KHI
ký hợp đồng + chứng thực developer (tài liệu nằm sau đăng nhập open.jtexpress.vn).
Code dưới là KHUNG theo chuẩn chung của J&T Open Platform (tham khảo tích hợp
các nước); path/field dưới lấy từ tài liệu partner, KHÔNG dùng làm căn cứ
production khi chưa có tài liệu VN chính thức.

BẮT BUỘC trước khi dùng:
1. Ký hợp đồng với J&T Express Việt Nam (không có đường tự đăng ký).
2. Nhận mã khách hàng (customer code) do bưu cục đối tác cấp.
3. Đăng ký + chứng thực developer tại https://open.jtexpress.vn.

creds cần: api_account, customer_code, private_key (ký request).
"""
import hashlib
import json

import requests

from . import CarrierError as _BaseError
from . import items_summary


class CarrierError(_BaseError):
    pass


# 🔴 CHƯA KIỂM CHỨNG cho thị trường VN — cần xác nhận lại trong tài liệu Partner.
API_BASE = "https://open.jtexpress.vn"
CREATE_PATH = "/webopenplatformapi/api/order/addOrder"   # 🔴 CHƯA KIỂM CHỨNG
TRACK_PATH = "/webopenplatformapi/api/order/queryTrack"  # 🔴 CHƯA KIỂM CHỨNG
TIMEOUT = 30

UNVERIFIED = ("Endpoint J&T cho thị trường VN CHƯA KIỂM CHỨNG "
              "(tài liệu chi tiết nằm sau đăng nhập open.jtexpress.vn). "
              "Đối chiếu tài liệu Partner trước khi dùng.")

NEED_CONTRACT = ("J&T Express yêu cầu ký hợp đồng và customer code do bưu cục cấp. "
                 "Vào Cài đặt → Vận chuyển để nhập API account, customer code và private key.")


def _require_creds(creds):
    api_account = (creds.get("api_account") or "").strip()
    customer_code = (creds.get("customer_code") or "").strip()
    private_key = (creds.get("private_key") or "").strip()
    if not api_account or not customer_code or not private_key:
        raise CarrierError(NEED_CONTRACT)
    return api_account, customer_code, private_key


def _sign(payload_str, private_key):
    """Ký request theo chuẩn J&T Open Platform (MD5 của payload + private key)."""
    raw = (payload_str + private_key).encode("utf-8")
    return hashlib.md5(raw).hexdigest().upper()


def _build_order_payload(order, api_account, customer_code):
    content, _qty = items_summary(order)
    return {
        "apiAccount": api_account,
        "customerCode": customer_code,
        "orderSn": f"SHOPDESK-{order.get('id')}",
        "receiver": {
            "name": order.get("customer_name") or "",
            "mobile": order.get("phone") or "",
            "address": order.get("address") or "",
        },
        "items": [{"name": content[:255], "weight": int(order.get("weight") or 500)}],
        "codAmount": int(order.get("total") or 0),
        "remark": order.get("notes") or "",
    }


def create_shipment(order, creds):
    api_account, customer_code, private_key = _require_creds(creds)
    payload = _build_order_payload(order, api_account, customer_code)
    payload_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    body = {
        "data": payload_str,
        "sign": _sign(payload_str, private_key),
        "apiAccount": api_account,
    }
    try:
        resp = requests.post(API_BASE + CREATE_PATH, json=body, timeout=TIMEOUT)
        data = resp.json()
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới J&T: {e.__class__.__name__}. {UNVERIFIED}")
    except ValueError:
        raise CarrierError(f"J&T trả dữ liệu không hợp lệ. {UNVERIFIED}")
    code = (data.get("billCode") or data.get("mailNo") or data.get("trackingNumber")
            or (data.get("data") or {}).get("billCode"))
    if not code:
        raise CarrierError(
            f"J&T không trả mã vận đơn: {str(data)[:200]}. {UNVERIFIED}"
        )
    return str(code)


def track(code, creds):
    _require_creds(creds)
    raise CarrierError(
        f"Tra cứu J&T: path tracking cho VN CHƯA KIỂM CHỨNG. {UNVERIFIED} "
        f"Tra cứu tay tại jtexpress.vn với mã {code}."
    )


def test_connection(creds):
    _require_creds(creds)
    return ("Đã nhập đủ API account + customer code + private key. " + UNVERIFIED)
