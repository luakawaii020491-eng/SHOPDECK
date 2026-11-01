#!/usr/bin/env python3
"""Tích hợp Best Express (BEST Inc Việt Nam).

🔴 CHƯA KIỂM CHỨNG — Best Express KHÔNG công bố tài liệu API gốc công khai.
Tài liệu chi tiết chỉ được cấp cho đối tác SAU KHI ký hợp đồng / kích hoạt
tài khoản với bộ phận kinh doanh của hãng. Vì vậy KHÔNG gọi bất kỳ endpoint
gốc nào khi chưa có tài liệu chính thức — code dưới là KHUNG chuẩn bị sẵn.

Những gì ĐÃ xác minh được (nghiên cứu 01/11/2026):
- 🟡 Xác thực tích hợp theo tài liệu Sapo (support.sapo.vn/best-express):
  dùng TÊN ĐĂNG NHẬP + MẬT KHẨU tài khoản BEST (định dạng V9Cus… hoặc cus...),
  tài khoản phải được KÍCH HOẠT trước (liên hệ hotline 1900 1031 hoặc
  (028) 730 86998 gặp bộ phận kinh doanh).
- 🟡 Tra cứu vận đơn công khai tại bestexpress.vn (tới 20 mã/lần), Zalo OA
  "BEST Express Vietnam", hotline 1900 1031.
- 🔴 Endpoint tạo đơn / tra cứu API gốc: CHƯA XÁC MINH (không công bố công khai).

BẮT BUỘC trước khi dùng API gốc:
1. Liên hệ bộ phận kinh doanh Best Express (1900 1031) để ký hợp đồng /
   kích hoạt tài khoản và xin tài liệu API đối tác.
2. Đối chiếu tài liệu hãng rồi mới bật create_shipment() bên dưới.

creds cần: username (định dạng V9Cus…/cus...), password.
"""
from . import CarrierError as _BaseError


class CarrierError(_BaseError):
    pass


TIMEOUT = 30

UNVERIFIED = ("API gốc của Best Express cho VN CHƯA KIỂM CHỨNG "
              "(hãng không công bố tài liệu công khai; tài liệu chi tiết "
              "chỉ cấp cho đối tác sau ký hợp đồng). "
              "Đối chiếu tài liệu từ bộ phận kinh doanh Best Express trước khi dùng.")

NEED_ACTIVATION = ("Best Express yêu cầu tài khoản đã được kích hoạt "
                   "(tên đăng nhập định dạng V9Cus… hoặc cus...). "
                   "Liên hệ hotline 1900 1031 (hoặc (028) 730 86998 — bộ phận kinh doanh) "
                   "để kích hoạt và xin tài liệu API đối tác. "
                   "Sau đó vào Cài đặt → Vận chuyển để nhập tên đăng nhập + mật khẩu.")


def _require_creds(creds):
    username = (creds.get("username") or "").strip()
    password = (creds.get("password") or "").strip()
    if not username or not password:
        raise CarrierError(
            "Chưa nhập tài khoản Best Express. " + NEED_ACTIVATION
        )
    return username, password


def create_shipment(order, creds):
    _require_creds(creds)
    # 🔴 KHÔNG gọi endpoint: path tạo đơn API gốc của Best Express chưa được
    # hãng công bố công khai. Gửi request đến URL đoán mò là rủi ro (đơn thật
    # có thể bị tạo sai / lộ thông tin khách hàng). Chờ tài liệu chính thức.
    raise CarrierError(
        "Tạo đơn Best Express qua API CHƯA KHẢ DỤNG: " + UNVERIFIED + " "
        "Tạm thời tạo đơn tay trên website/app Best Express."
    )


def track(code, creds):
    # 🔴 Endpoint tra cứu API gốc chưa xác minh; hướng dẫn tra cứu công khai.
    raise CarrierError(
        f"Tra cứu Best Express: endpoint API gốc CHƯA KIỂM CHỨNG. {UNVERIFIED} "
        f"Tra cứu tay mã {code} tại bestexpress.vn, Zalo OA 'BEST Express Vietnam' "
        f"hoặc hotline 1900 1031."
    )


def test_connection(creds):
    username, _password = _require_creds(creds)
    # Chưa thể xác minh đăng nhập thật vì endpoint auth của API gốc
    # chưa được hãng công bố — chỉ kiểm tra định dạng tên đăng nhập.
    uname_lower = username.lower()
    if not (uname_lower.startswith("v9cus") or uname_lower.startswith("cus")):
        return ("Đã nhập đủ tên đăng nhập + mật khẩu. Lưu ý: tên đăng nhập BEST "
                "thường có dạng V9Cus… hoặc cus... — hãy kiểm tra lại định dạng. "
                + UNVERIFIED)
    return ("Đã nhập đủ tên đăng nhập + mật khẩu Best Express. " + UNVERIFIED)
