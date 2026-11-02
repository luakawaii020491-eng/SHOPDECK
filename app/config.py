#!/usr/bin/env python3
"""Đọc/ghi config.json của ShopDesk.

QUAN TRỌNG: không bao giờ log token/key ra console hay file log.
"""
import copy
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "pages": [],  # [{"page_id": "...", "name": "...", "token": "..."}]
    "shipping": {
        "ghn": {},          # api_key, shop_id, default_ward_code, default_district_id
        "ghtk": {},         # api_key, partner_code, pick_name, pick_address, pick_province, pick_district, pick_tel
        "viettelpost": {},  # username, password, groupaddress_id, cus_id
        "jt": {},           # api_account, customer_code, private_key
        "best": {},         # username, password
    },
    # Thông tin người gửi — in trên tem/phiếu giao hàng (trang Cài đặt > mục "Người gửi")
    "sender": {
        "shop_name": "",
        "sender_phone": "",
        "sender_address": "",
    },
}

# Env var cho thông tin người gửi (deploy cloud: sống qua redeploy):
#   SHOPDESK_SENDER_JSON = '{"shop_name":"...","sender_phone":"...","sender_address":"..."}'
SENDER_ENV_VAR = "SHOPDESK_SENDER_JSON"

CARRIERS = ["ghn", "ghtk", "viettelpost", "jt", "best"]

# Biến môi trường (dùng khi deploy lên host như Render — không lưu token vào repo):
#   SHOPDESK_PAGES_JSON = '[{"page_id":"441747482366131","name":"Dép Hana","token":"..."}, ...]'
#   SHOPDESK_SHIPPING_JSON = '{"jt":{"api_account":"...","customer_code":"...","api_key":"..."}}'
PAGES_ENV_VAR = "SHOPDESK_PAGES_JSON"
SHIPPING_ENV_VAR = "SHOPDESK_SHIPPING_JSON"


def load_config():
    """Đọc config.json; tự tạo file mặc định nếu chưa có."""
    if not os.path.exists(CONFIG_PATH):
        save_config(copy.deepcopy(DEFAULT_CONFIG))
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        cfg = {}
    # Bổ sung key còn thiếu từ default (không ghi đè giá trị đã có)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(cfg, dict):
        merged["pages"] = cfg.get("pages", []) or []
        ship = cfg.get("shipping", {}) or {}
        for c in CARRIERS:
            if isinstance(ship.get(c), dict):
                merged["shipping"][c].update(ship[c])
        sender = cfg.get("sender") or {}
        if isinstance(sender, dict):
            for k in merged["sender"]:
                if isinstance(sender.get(k), str) and sender[k].strip():
                    merged["sender"][k] = sender[k].strip()
    # Gộp danh sách page từ biến môi trường vào (deploy cloud: token trong env
    # sống qua mỗi lần deploy, không phải nhập lại). Env thắng khi trùng page_id;
    # page chỉ có trong file (thêm qua trang Settings) vẫn hiện bình thường.
    # LƯU Ý: xóa page đang có trong env thì phải sửa env var — xóa ở Settings
    # chỉ có tác dụng với page thêm qua Settings.
    env_pages = os.environ.get(PAGES_ENV_VAR, "").strip()
    if env_pages:
        try:
            parsed = json.loads(env_pages)
            if isinstance(parsed, list) and parsed:
                by_id = {str(p.get("page_id")): p for p in merged["pages"]
                         if p.get("page_id")}
                for p in parsed:
                    if isinstance(p, dict) and p.get("page_id"):
                        by_id[str(p["page_id"])] = {
                            "page_id": str(p.get("page_id", "")),
                            "name": p.get("name", "") or "",
                            "token": p.get("token", "") or "",
                        }
                merged["pages"] = list(by_id.values())
        except (json.JSONDecodeError, ValueError):
            pass
    # Gộp thông tin hãng vận chuyển từ biến môi trường (deploy cloud: key sống qua
    # mỗi lần deploy, không phải nhập lại; env thắng từng field khi trùng hãng).
    env_ship = os.environ.get(SHIPPING_ENV_VAR, "").strip()
    if env_ship:
        try:
            parsed = json.loads(env_ship)
            if isinstance(parsed, dict):
                for carrier, fields in parsed.items():
                    if carrier in CARRIERS and isinstance(fields, dict):
                        for k, v in fields.items():
                            if isinstance(v, str) and v.strip():
                                merged["shipping"][carrier][k] = v.strip()
        except (json.JSONDecodeError, ValueError):
            pass
    # Gộp thông tin người gửi từ biến môi trường (deploy cloud: sống qua redeploy)
    env_sender = os.environ.get(SENDER_ENV_VAR, "").strip()
    if env_sender:
        try:
            parsed = json.loads(env_sender)
            if isinstance(parsed, dict):
                for k in merged["sender"]:
                    v = parsed.get(k)
                    if isinstance(v, str) and v.strip():
                        merged["sender"][k] = v.strip()
        except (json.JSONDecodeError, ValueError):
            pass
    return merged


def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


# ---- Pages ----

def list_pages():
    return load_config().get("pages", [])


def get_page(page_id):
    for p in list_pages():
        if str(p.get("page_id")) == str(page_id):
            return p
    return None


def add_page(page_id, name, token):
    cfg = load_config()
    cfg["pages"] = [p for p in cfg["pages"] if str(p.get("page_id")) != str(page_id)]
    cfg["pages"].append({"page_id": str(page_id), "name": name or "", "token": token or ""})
    save_config(cfg)


def delete_page(page_id):
    cfg = load_config()
    cfg["pages"] = [p for p in cfg["pages"] if str(p.get("page_id")) != str(page_id)]
    save_config(cfg)


# ---- Shipping credentials ----

def get_shipping_creds(carrier):
    cfg = load_config()
    return dict(cfg.get("shipping", {}).get(carrier, {}) or {})


def set_shipping_creds(carrier, fields):
    if carrier not in CARRIERS:
        raise ValueError(f"Hãng vận chuyển không hợp lệ: {carrier}")
    cfg = load_config()
    cur = cfg["shipping"].get(carrier, {}) or {}
    for k, v in (fields or {}).items():
        if isinstance(v, str):
            v = v.strip()
        # Chuỗi rỗng = xóa field đó (cho phép gỡ key cũ)
        if v == "" or v is None:
            cur.pop(k, None)
        else:
            cur[k] = v
    cfg["shipping"][carrier] = cur
    save_config(cfg)


def shipping_status_masked():
    """Trạng thái cài đặt từng hãng — chỉ trả về *_set, KHÔNG trả key thật."""
    cfg = load_config()
    out = {}
    for c in CARRIERS:
        creds = cfg.get("shipping", {}).get(c, {}) or {}
        out[c] = {f"{k}_set": bool(v) for k, v in creds.items()}
    return out


# ---- Thông tin người gửi (in trên tem/phiếu giao hàng) ----

SENDER_FIELDS = ["shop_name", "sender_phone", "sender_address"]


def get_sender():
    """Trả về dict thông tin người gửi (đã gộp env var)."""
    return dict(load_config().get("sender", {}) or {})


def set_sender(fields):
    cfg = load_config()
    cur = cfg.get("sender") or {}
    for k, v in (fields or {}).items():
        if k not in SENDER_FIELDS:
            continue
        v = str(v or "").strip()
        cur[k] = v
    cfg["sender"] = cur
    save_config(cfg)
    return cur
