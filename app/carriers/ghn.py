#!/usr/bin/env python3
"""Tích hợp GHN — Giao Hàng Nhanh.

Xác minh: ✅ (developer.ghn.vn, nghiên cứu 31/10/2026)
- Base: https://online-gateway.ghn.vn, prefix /shiip/public-api/
- Auth: header Token: <API_TOKEN> + ShopId: <SHOP_ID>
- Tạo đơn: POST /shiip/public-api/v2/shipping-order/create → data.order_code
- Dùng client_order_code để chống trùng đơn khi retry.

creds cần: api_key, shop_id (+ default_ward_code, default_district_id để tạo đơn
vì GHN bắt buộc mã phường/xã + quận/huyện theo danh mục của GHN).
"""
import requests

from . import CarrierError as _BaseError
from . import items_summary


class CarrierError(_BaseError):
    pass


API_BASE = "https://online-gateway.ghn.vn"
TIMEOUT = 30

# Mã trạng thái GHN → tiếng Việt (tài liệu developer.ghn.vn)
STATUS_VI = {
    "ready_to_pick": "Chờ lấy hàng",
    "picking": "Đang lấy hàng",
    "money_collect_picking": "Đang lấy hàng (thu hộ)",
    "picked": "Đã lấy hàng",
    "storing": "Đang lưu kho",
    "transporting": "Đang trung chuyển",
    "sorting": "Đang phân loại",
    "delivering": "Đang giao hàng",
    "money_collect_delivering": "Đang giao hàng (thu hộ)",
    "delivered": "Đã giao hàng",
    "delivery_fail": "Giao thất bại",
    "waiting_to_return": "Chờ trả hàng",
    "return": "Đang trả hàng",
    "return_transporting": "Đang vận chuyển trả hàng",
    "return_sorting": "Đang phân loại trả hàng",
    "returning": "Đang trả hàng",
    "returned": "Đã trả hàng",
    "cancel": "Đã hủy",
    "exception": "Ngoại lệ",
    "damage": "Hàng hư hỏng",
    "lost": "Thất lạc",
}


def _headers(creds):
    return {
        "Token": creds.get("api_key", ""),
        "ShopId": str(creds.get("shop_id", "")),
        "Content-Type": "application/json",
    }


def _post(path, creds, body):
    try:
        resp = requests.post(API_BASE + path, headers=_headers(creds), json=body, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới GHN: {e.__class__.__name__}")
    try:
        data = resp.json()
    except ValueError:
        raise CarrierError(f"GHN trả dữ liệu không hợp lệ (HTTP {resp.status_code}).")
    return data


def create_shipment(order, creds):
    api_key = (creds.get("api_key") or "").strip()
    shop_id = (creds.get("shop_id") or "").strip()
    if not api_key or not shop_id:
        raise CarrierError("Chưa nhập API key GHN. Vào Cài đặt → Vận chuyển để nhập.")
    to_ward_code = str(order.get("to_ward_code") or creds.get("default_ward_code") or "").strip()
    to_district_id = str(order.get("to_district_id") or creds.get("default_district_id") or "").strip()
    if not to_ward_code or not to_district_id:
        raise CarrierError(
            "GHN yêu cầu mã phường/xã và quận/huyện theo danh mục GHN. "
            "Nhập 'Mã phường/xã mặc định' và 'Mã quận/huyện mặc định' trong Cài đặt → Vận chuyển (GHN)."
        )
    content, _qty = items_summary(order)
    body = {
        "to_name": order.get("customer_name") or "",
        "to_phone": order.get("phone") or "",
        "to_address": order.get("address") or "",
        "to_ward_code": to_ward_code,
        "to_district_id": int(to_district_id),
        "weight": int(order.get("weight") or 500),  # gram
        "service_type_id": 2,      # 2 = hàng nhẹ
        "payment_type_id": 1,      # 1 = shop trả cước
        "required_note": "CHOTHUHANG",  # cho xem hàng (khách được kiểm tra hàng)
        "client_order_code": f"SHOPDESK-{order.get('id')}",
        "cod_amount": int(order.get("total") or 0),
        "content": content,
    }
    data = _post("/shiip/public-api/v2/shipping-order/create", creds, body)
    if data.get("code") != 200:
        raise CarrierError(f"GHN từ chối tạo đơn: {str(data.get('message') or data.get('code'))[:200]}")
    order_code = (data.get("data") or {}).get("order_code")
    if not order_code:
        raise CarrierError("GHN không trả mã vận đơn. Vui lòng kiểm tra lại trên khachhang.ghn.vn.")
    return str(order_code)


def track(code, creds):
    api_key = (creds.get("api_key") or "").strip()
    if not api_key:
        raise CarrierError("Chưa nhập API key GHN. Vào Cài đặt → Vận chuyển để nhập.")
    data = _post("/shiip/public-api/v2/shipping-order/detail", creds, {"order_code": code})
    if data.get("code") != 200:
        raise CarrierError(f"GHN không tìm thấy vận đơn {code}.")
    info = data.get("data") or {}
    status = info.get("status") or ""
    status_vi = STATUS_VI.get(status, status or "Không rõ trạng thái")
    history = []
    for log in info.get("logs") or []:
        st = log.get("status") or ""
        history.append({
            "time": str(log.get("updated_date") or log.get("created_date") or ""),
            "desc": STATUS_VI.get(st, st or "Cập nhật trạng thái"),
        })
    if not history:
        history = [{"time": "", "desc": status_vi}]
    return {"status_vi": status_vi, "history": history}


def test_connection(creds):
    api_key = (creds.get("api_key") or "").strip()
    if not api_key:
        raise CarrierError("Chưa nhập API key GHN. Vào Cài đặt → Vận chuyển để nhập.")
    try:
        resp = requests.get(
            API_BASE + "/shiip/public-api/v2/shop/all",
            headers={"Token": api_key, "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới GHN: {e.__class__.__name__}")
    if resp.status_code == 401:
        raise CarrierError("API key GHN không hợp lệ (401). Kiểm tra lại token.")
    try:
        data = resp.json()
    except ValueError:
        raise CarrierError("GHN trả dữ liệu không hợp lệ.")
    if data.get("code") == 200:
        return "Kết nối GHN thành công."
    raise CarrierError(f"GHN từ chối: {str(data.get('message') or data.get('code'))[:200]}")
