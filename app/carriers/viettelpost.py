#!/usr/bin/env python3
"""Tích hợp Viettel Post.

⚠️ CẦN ĐỐI CHIẾU LẠI TÀI LIỆU PARTNER TRƯỚC KHI DÙNG PRODUCTION.
Viettel Post không công bố tài liệu API công khai. Các endpoint dưới đây lấy từ
blog kỹ thuật trích tài liệu chính thức + sandbox mô phỏng luồng thật (EzyPlatform),
kiểm tra 08/10/2026 — CHƯA xác minh từ tài liệu chính thức:
- Base: https://partner.viettelpost.vn (API v2)
- Login: POST /user/login → token tạm; POST /user/ownerconnect → token dài hạn (1 năm)
- Tạo đơn: POST /order/createOrder (path CHƯA xác minh)
- Tra cứu hành trình: path CHƯA xác minh → track() báo lỗi hướng dẫn đối chiếu tài liệu.

creds cần: username, password (tài khoản Partner), groupaddress_id, cus_id
(lấy từ API user/listInventory sau khi login).
"""
import requests

from . import CarrierError as _BaseError
from . import items_summary


class CarrierError(_BaseError):
    pass


API_BASE = "https://partner.viettelpost.vn"
TIMEOUT = 30

NEEDS_RECHECK = ("Cần đối chiếu lại tài liệu trong tài khoản Partner Viettel Post "
                 "trước khi dùng production.")


def _login(creds):
    """Login 2 bước → token dài hạn (1 năm)."""
    username = (creds.get("username") or "").strip()
    password = (creds.get("password") or "").strip()
    if not username or not password:
        raise CarrierError("Chưa nhập tài khoản Viettel Post. Vào Cài đặt → Vận chuyển để nhập.")
    try:
        r1 = requests.post(API_BASE + "/user/login",
                           json={"USERNAME": username, "PASSWORD": password},
                           timeout=TIMEOUT)
        d1 = r1.json()
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới Viettel Post: {e.__class__.__name__}")
    except ValueError:
        raise CarrierError("Viettel Post trả dữ liệu không hợp lệ khi đăng nhập.")
    tmp_token = ((d1.get("data") or {}).get("token")) if isinstance(d1, dict) else None
    if not tmp_token:
        raise CarrierError("Đăng nhập Viettel Post thất bại. Kiểm tra lại tài khoản/mật khẩu.")
    try:
        r2 = requests.post(API_BASE + "/user/ownerconnect", json={"TOKEN": tmp_token},
                           timeout=TIMEOUT)
        d2 = r2.json()
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới Viettel Post: {e.__class__.__name__}")
    except ValueError:
        raise CarrierError("Viettel Post trả dữ liệu không hợp lệ.")
    token = ((d2.get("data") or {}).get("token")) if isinstance(d2, dict) else None
    if not token:
        raise CarrierError("Không lấy được token dài hạn Viettel Post. " + NEEDS_RECHECK)
    return token


def create_shipment(order, creds):
    """Tạo đơn Viettel Post. Endpoint /order/createOrder CHƯA xác minh — cần đối chiếu."""
    token = _login(creds)
    group_id = (creds.get("groupaddress_id") or "").strip()
    cus_id = (creds.get("cus_id") or "").strip()
    if not group_id or not cus_id:
        raise CarrierError(
            "Thiếu GROUPADDRESS_ID/CUS_ID (kho lấy hàng). "
            "Lấy từ API user/listInventory trong tài khoản Partner rồi nhập vào Cài đặt."
        )
    content, _qty = items_summary(order)
    body = {
        "ORDER_NUMBER": f"SHOPDESK-{order.get('id')}",
        "GROUPADDRESS_ID": group_id,
        "CUS_ID": cus_id,
        "RECEIVER_FULLNAME": order.get("customer_name") or "",
        "RECEIVER_PHONE": order.get("phone") or "",
        "RECEIVER_ADDRESS": order.get("address") or "",
        "PRODUCT_NAME": content[:255],
        "PRODUCT_WEIGHT": int(order.get("weight") or 500),  # gram
        "MONEY_COLLECTION": int(order.get("total") or 0),   # tiền thu hộ COD
        "PRODUCT_PRICE": int(order.get("total") or 0),
        "NOTE": order.get("notes") or "",
    }
    try:
        resp = requests.post(API_BASE + "/order/createOrder",
                             headers={"Token": token, "Content-Type": "application/json"},
                             json=body, timeout=TIMEOUT)
        data = resp.json()
    except requests.RequestException as e:
        raise CarrierError(f"Không kết nối được tới Viettel Post: {e.__class__.__name__}")
    except ValueError:
        raise CarrierError("Viettel Post trả dữ liệu không hợp lệ.")
    # Cấu trúc response chưa xác minh — parse phòng thủ nhiều tên field
    payload = data.get("data") if isinstance(data, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    code = (payload.get("ORDER_NUMBER") or payload.get("order_number")
            or payload.get("TRACKING_CODE") or payload.get("tracking_code")
            or payload.get("BILL_CODE") or payload.get("bill_code"))
    if not code:
        raise CarrierError(
            "Viettel Post không trả mã vận đơn (cấu trúc response chưa xác minh). " + NEEDS_RECHECK
        )
    return str(code)


def track(code, creds):
    """Path tra cứu hành trình CHƯA xác minh — không đoán endpoint."""
    raise CarrierError(
        f"Tra cứu hành trình Viettel Post: path API chưa được xác minh từ tài liệu công khai. "
        f"{NEEDS_RECHECK} Tra cứu tay tại viettelpost.vn với mã {code}."
    )


def test_connection(creds):
    """Test = thử login 2 bước."""
    _login(creds)
    return "Đăng nhập Viettel Post thành công. " + NEEDS_RECHECK
