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
}

CARRIERS = ["ghn", "ghtk", "viettelpost", "jt", "best"]

# Biến môi trường (dùng khi deploy lên host như Render — không lưu token vào repo):
#   SHOPDESK_PAGES_JSON = '[{"page_id":"441747482366131","name":"Dép Hana","token":"..."}, ...]'
PAGES_ENV_VAR = "SHOPDESK_PAGES_JSON"


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
    # Ghi đè danh sách page từ biến môi trường (deploy cloud: token sống qua
    # mỗi lần deploy, không phải nhập lại; vẫn chỉnh được ở trang Settings).
    env_pages = os.environ.get(PAGES_ENV_VAR, "").strip()
    if env_pages:
        try:
            parsed = json.loads(env_pages)
            if isinstance(parsed, list) and parsed:
                merged["pages"] = [
                    {"page_id": str(p.get("page_id", "")),
                     "name": p.get("name", "") or "",
                     "token": p.get("token", "") or ""}
                    for p in parsed if isinstance(p, dict) and p.get("page_id")
                ]
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
