#!/usr/bin/env python3
"""Routes vận chuyển + cài đặt: /api/shipping/<carrier>/* và /api/settings/*."""
from flask import Blueprint, jsonify, request

from . import config as config_mod
from . import db as db_mod
from . import products as products_mod
from . import tags as tags_mod
from .carriers import CARRIER_NAMES, CARRIERS, CarrierError
from .carriers import ghn, ghtk, viettelpost, jt, best

shipping_bp = Blueprint("shipping", __name__)

MODULES = {"ghn": ghn, "ghtk": ghtk, "viettelpost": viettelpost, "jt": jt, "best": best}


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


def _check_carrier(carrier):
    if carrier not in CARRIERS:
        return _err(f"Hãng vận chuyển không hợp lệ: {carrier}. Chọn trong: {', '.join(CARRIERS)}.")
    return None


def _order_weight_grams(order):
    """Tính tổng trọng lượng (gram) từ items của đơn qua bảng products.

    items trong đơn có dạng [{"sku": ..., "qty": ...}]. Nếu một SKU chưa có
    trọng lượng hoặc không còn trong bảng products → trả None (hãng VC
    sẽ dùng trọng lượng mặc định của nó).
    """
    import json
    try:
        items = order.get("items")
        if isinstance(items, str):
            items = json.loads(items or "[]")
    except Exception:
        return None
    total = 0
    found = False
    for it in items or []:
        if not isinstance(it, dict):
            continue
        sku = str(it.get("sku") or "").strip()
        try:
            qty = int(it.get("qty") or 0)
        except (TypeError, ValueError):
            qty = 0
        if not sku or qty <= 0:
            continue
        prod = products_mod.get_by_sku(sku)
        w = (prod or {}).get("weight_grams")
        if w is None:
            return None
        try:
            w = int(w)
        except (TypeError, ValueError):
            return None
        total += w * qty
        found = True
    return total if found else None


def create_shipment_for_order(order_id, carrier, weight_grams=None):
    """Tạo vận đơn cho đơn hàng — dùng chung cho route và quick-order.

    weight_grams: trọng lượng tính sẵn (gram). Nếu không truyền, tự tra
    từ bảng products theo SKU trong đơn. Nếu vẫn không có, các module
    carrier dùng mặc định của chúng (hiện tại 500g).

    Trả về mã vận đơn. Raise ValueError với message tiếng Việt khi lỗi.
    """
    if carrier not in CARRIERS:
        raise ValueError(
            f"Hãng vận chuyển không hợp lệ: {carrier}. Chọn trong: {', '.join(CARRIERS)}.")
    order = db_mod.get_order(order_id)
    if not order:
        raise ValueError("Không tìm thấy đơn hàng.")
    if order.get("shipping_code"):
        raise ValueError(
            f"Đơn này đã có mã vận đơn {order['shipping_code']} "
            f"({CARRIER_NAMES.get(carrier)}).")
    # Đưa trọng lượng thực vào dict tạm cho carrier dùng (order.get("weight"))
    weight = None
    try:
        weight = int(weight_grams) if weight_grams is not None else None
    except (TypeError, ValueError):
        weight = None
    if not weight or weight <= 0:
        weight = _order_weight_grams(order)
    if weight and weight > 0:
        order["weight"] = weight
    creds = config_mod.get_shipping_creds(carrier)
    module = MODULES[carrier]
    try:
        code = module.create_shipment(order, creds)
    except CarrierError as e:
        # Ghi lịch sử thất bại — giữ nguyên văn message tiếng Việt của hãng
        db_mod.log_shipment_attempt(order_id, carrier, False, str(e))
        raise ValueError(str(e))
    except Exception as e:
        msg = (f"Lỗi không xác định khi tạo đơn {CARRIER_NAMES.get(carrier)}: "
               f"{e.__class__.__name__}")
        db_mod.log_shipment_attempt(order_id, carrier, False, msg)
        raise ValueError(msg)
    db_mod.update_order(order_id, {
        "shipping_carrier": carrier,
        "shipping_code": code,
        "status": "shipped",
    })
    # Ghi lịch sử thành công
    db_mod.log_shipment_attempt(
        order_id, carrier, True,
        f"Đã tạo vận đơn {CARRIER_NAMES.get(carrier)}: {code}")
    # Auto-tag: đơn đã đẩy sang ĐVVC (gỡ "chua_chot" nếu có)
    try:
        tags_mod.auto_tag_shipped(order.get("source_thread") or "")
    except Exception:
        pass
    return code


# ---- Tạo đơn vận chuyển ----

@shipping_bp.post("/api/shipping/<carrier>/create")
def create_shipment(carrier):
    err = _check_carrier(carrier)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")
    if not order_id:
        return _err("Thiếu order_id.")
    try:
        code = create_shipment_for_order(order_id, carrier)
    except ValueError as e:
        return jsonify({"ok": False, "error_vi": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error_vi": f"Lỗi không xác định khi tạo đơn {CARRIER_NAMES.get(carrier)}: {e.__class__.__name__}"})
    return jsonify({"ok": True, "code": code})


@shipping_bp.post("/api/shipments/bulk")
def bulk_create_shipments():
    """Đẩy vận đơn hàng loạt: {"order_ids": [1,2,3], "carrier": "jt"}.

    - carrier phải thuộc CARRIERS; tối đa 100 đơn/lần.
    - Đơn đã có shipping_code → bỏ qua (skipped, không đẩy lại).
    - Lỗi từng đơn không làm dừng cả loạt. Lịch sử đẩy đơn vẫn được ghi
      qua create_shipment_for_order (shipment_attempts).
    """
    body = request.get_json(silent=True) or {}
    carrier = str(body.get("carrier") or "").strip().lower()
    if carrier not in CARRIERS:
        return _err(f"Hãng vận chuyển không hợp lệ: {carrier or '?'}. Chọn trong: {', '.join(CARRIERS)}.")
    raw_ids = body.get("order_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return _err("Chưa chọn đơn nào để đẩy (order_ids trống).")
    order_ids = []
    seen = set()
    for x in raw_ids:
        try:
            oid = int(x)
        except (TypeError, ValueError):
            return _err(f"order_id không hợp lệ: {x}.")
        if oid <= 0:
            return _err(f"order_id không hợp lệ: {x}.")
        if oid not in seen:
            seen.add(oid)
            order_ids.append(oid)
    if len(order_ids) > 100:
        return _err("Mỗi lần chỉ đẩy tối đa 100 đơn. Hãy chia thành nhiều lượt.")

    results = []
    n_ok = n_fail = n_skip = 0
    for oid in order_ids:
        order = db_mod.get_order(oid)
        if order is None:
            results.append({"order_id": oid, "ok": False,
                            "error_vi": "Không tìm thấy đơn hàng."})
            n_fail += 1
            continue
        if order.get("shipping_code"):
            results.append({"order_id": oid, "ok": False, "skipped": True,
                            "error_vi": "Đã có mã vận đơn "
                                        f"{order['shipping_code']} — bỏ qua, không đẩy lại."})
            n_skip += 1
            continue
        try:
            code = create_shipment_for_order(oid, carrier)
        except ValueError as e:
            results.append({"order_id": oid, "ok": False, "error_vi": str(e)})
            n_fail += 1
        except Exception as e:
            results.append({"order_id": oid, "ok": False,
                            "error_vi": f"Lỗi không xác định: {e.__class__.__name__}"})
            n_fail += 1
        else:
            results.append({"order_id": oid, "ok": True, "shipping_code": code})
            n_ok += 1
    return jsonify({
        "ok": True,
        "carrier": carrier,
        "results": results,
        "summary": {"total": len(order_ids), "success": n_ok,
                    "failed": n_fail, "skipped": n_skip},
    })


@shipping_bp.get("/api/shipping/<carrier>/track")
def track_shipment(carrier):
    err = _check_carrier(carrier)
    if err:
        return err
    code = (request.args.get("code") or "").strip()
    if not code:
        return _err("Thiếu mã vận đơn (code).")
    creds = config_mod.get_shipping_creds(carrier)
    module = MODULES[carrier]
    try:
        result = module.track(code, creds)
    except CarrierError as e:
        return jsonify({"ok": False, "error_vi": str(e)})
    except Exception as e:
        return jsonify({"ok": False, "error_vi": f"Lỗi không xác định khi tra cứu: {e.__class__.__name__}"})
    return jsonify({"ok": True, "status_vi": result.get("status_vi", ""),
                    "history": result.get("history", [])})


# ---- Lịch sử đẩy đơn ----

@shipping_bp.get("/api/shipping/attempts")
def list_attempts():
    """Lịch sử đẩy đơn sang ĐVVC (mới nhất trước). ?order_id= để lọc theo đơn."""
    order_id = request.args.get("order_id") or None
    try:
        limit = int(request.args.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    attempts = db_mod.list_shipment_attempts(order_id=order_id, limit=limit)
    return jsonify({"attempts": attempts})


# ---- Cài đặt ----

@shipping_bp.get("/api/settings")
def get_settings():
    # Chỉ trả về trạng thái *_set — KHÔNG bao giờ trả key thật.
    return jsonify({"shipping": config_mod.shipping_status_masked(),
                    "carriers": CARRIER_NAMES})


@shipping_bp.post("/api/settings/shipping/<carrier>")
def save_shipping_settings(carrier):
    err = _check_carrier(carrier)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _err("Dữ liệu cài đặt không hợp lệ.")
    try:
        config_mod.set_shipping_creds(carrier, body)
    except ValueError as e:
        return _err(str(e))
    return jsonify({"ok": True})


@shipping_bp.post("/api/settings/test")
def test_settings():
    body = request.get_json(silent=True) or {}
    kind = body.get("type")
    if kind == "page":
        page_id = str(body.get("page_id") or "").strip()
        page = config_mod.get_page(page_id)
        if not page or not page.get("token"):
            return jsonify({"ok": False, "msg": "Page chưa có token."})
        from .meta_client import MetaAPIError, MetaPageClient
        try:
            MetaPageClient(page_id, page["token"]).conversations(limit=1)
            return jsonify({"ok": True, "msg": f"Page '{page.get('name') or page_id}' kết nối OK."})
        except MetaAPIError as e:
            return jsonify({"ok": False, "msg": e.error_vi})
        except Exception:
            return jsonify({"ok": False, "msg": "Không kết nối được tới Meta. Thử lại sau."})
    if kind == "carrier":
        carrier = body.get("carrier")
        err = _check_carrier(carrier)
        if err:
            return err
        creds = config_mod.get_shipping_creds(carrier)
        try:
            msg = MODULES[carrier].test_connection(creds)
            return jsonify({"ok": True, "msg": msg})
        except CarrierError as e:
            return jsonify({"ok": False, "msg": str(e)})
        except Exception:
            return jsonify({"ok": False, "msg": "Lỗi không xác định khi kiểm tra kết nối."})
    return _err("type phải là 'page' hoặc 'carrier'.")
