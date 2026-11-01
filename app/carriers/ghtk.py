#!/usr/bin/env python3
"""Tích hợp GHTK — Giao Hàng Tiết Kiệm.

Xác minh: ✅ (đọc trực tiếp pro-docs.ghtk.vn, nghiên cứu 31/10/2026)
- Base: https://services.giaohangtietkiem.vn
- Auth: header Token: <API_TOKEN> + X-Client-Source: <PARTNER_CODE> (mã shop)
- Tạo đơn: POST /services/shipment/order → order.label (mã vận đơn dạng S1.A1.xxxxxxxx)
- Tra cứu: GET /services/shipment/v2/{label_id} → status_text (tiếng Việt)

creds cần: api_key, partner_code (mã shop), pick_name, pick_address, pick_province,
pick_district, pick_tel (thông tin lấy hàng).
"""
import requests

from . import CarrierError as _BaseError
from . import items_summary


class CarrierError(_BaseError):
    pass


API_BASE = "https://services.giaohangtietkiem.vn"
TIMEOUT = 30


def _headers(creds):
    return {
        "Token": creds.get("api_key", ""),
        "X-Client-Source": creds.get("partner_code", ""),
        "Content-Type": "application/json",
    }


def _handle(resp, action):
    try:
        data = resp.json()
    except ValueError:
        raise CarrierError(f"GHTK trả dữ liệu không hợp lệ (HTTP {resp.status_code}).")
    if resp.status_code == 401 or resp.status_code == 403:
        raise CarrierError("Token GHTK không hợp lệ hoặc thiếu quyền. Kiểm tra lại token và mã shop.")
    return data


def create_shipment(order, creds):
    token = (creds.get("api_key") or "").strip()
    partner = (creds.get("partner_code") or "").strip()
    if not token or not partner:
        raise CarrierError("Chưa nhập API key GHTK. Vào Cài đặt → Vận chuyển để nhập.")
    for field, label in [
        ("pick_name", "tên người gửi"), ("pick_address", "địa chỉ lấy hàng"),
        ("pick_province", "tỉnh/thành lấy hàng"), ("pick_district", "quận/huyện lấy hàng"),
        ("pick_tel", "SĐT lấy hàng"),
    ]:
        if not (creds.get(field) or "").strip():
            raise CarrierError(f"Thiếu thông tin lấy hàng GHTK ({label}). Vào Cài đặt → Vận chuyển để nhập.")
    content, qty = items_summary(order)
    total = int(order.get("total") or 0)
    body = {
        "products": [{
            "name": content[:255],
            "weight": float(order.get("weight") or 0.5) / 1000,  # kg
            "quantity": qty,
            "price": total,
        }],
        "order": {
            "id": f"SHOPDESK-{order.get('id')}",  # mã tham chiếu phía shop, chống trùng
            "pick_name": creds["pick_name"],
            "pick_money": total,          # tiền thu hộ COD
            "pick_address": creds["pick_address"],
            "pick_province": creds["pick_province"],
            "pick_district": creds["pick_district"],
            "pick_tel": creds["pick_tel"],
            "tel": order.get("phone") or "",
            "name": order.get("customer_name") or "",
            "address": order.get("address") or "",
            "province": creds.get("to_province") or order.get("province") or "",
            "district": creds.get("to_district") or order.get("district") or "",
            "hamlet": "Khác",
            "is_freeship": "1",
            "pick_option": "cod",
            "value": total,               # giá trị khai báo để tính bảo hiểm
            "note": order.get("notes") or "",
        },
    }
    try:
        resp = requests.post(API_BASE + "/services/shipment/order", headers=_headers(creds),
                             json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới GHTK: {e.__class__.__name__}")
    data = _handle(resp, "tạo đơn")
    if not data.get("success"):
        raise CarrierError(f"GHTK từ chối tạo đơn: {str(data.get('message') or 'lỗi không xác định')[:200]}")
    label = (data.get("order") or {}).get("label")
    if not label:
        raise CarrierError("GHTK không trả mã vận đơn.")
    return str(label)


def track(code, creds):
    token = (creds.get("api_key") or "").strip()
    if not token:
        raise CarrierError("Chưa nhập API key GHTK. Vào Cài đặt → Vận chuyển để nhập.")
    try:
        resp = requests.get(API_BASE + f"/services/shipment/v2/{code}", headers=_headers(creds),
                            timeout=TIMEOUT)
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới GHTK: {e.__class__.__name__}")
    data = _handle(resp, "tra cứu")
    order = data.get("order") or {}
    if not order and not data.get("success", True):
        raise CarrierError(f"GHTK không tìm thấy vận đơn {code}.")
    status_vi = order.get("status_text") or "Không rõ trạng thái"
    history = []
    for step in order.get("tracking") or order.get("logs") or []:
        if isinstance(step, dict):
            history.append({
                "time": str(step.get("time") or step.get("created") or ""),
                "desc": str(step.get("status_text") or step.get("desc") or ""),
            })
    if not history:
        history = [{"time": str(order.get("modified") or ""), "desc": status_vi}]
    return {"status_vi": status_vi, "history": history}


def test_connection(creds):
    token = (creds.get("api_key") or "").strip()
    if not token:
        raise CarrierError("Chưa nhập API key GHTK. Vào Cài đặt → Vận chuyển để nhập.")
    try:
        resp = requests.get(API_BASE + "/services/authenticated", headers=_headers(creds),
                            timeout=TIMEOUT)
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới GHTK: {e.__class__.__name__}")
    if resp.status_code in (401, 403):
        raise CarrierError("Token GHTK không hợp lệ hoặc đã hết hạn. Tạo token mới trên trang khách hàng GHTK.")
    try:
        data = resp.json()
    except ValueError:
        raise CarrierError("GHTK trả dữ liệu không hợp lệ.")
    if data.get("success"):
        return "Kết nối GHTK thành công."
    raise CarrierError(f"GHTK từ chối: {str(data.get('message') or 'lỗi không xác định')[:200]}")
